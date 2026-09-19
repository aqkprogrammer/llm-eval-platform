"""Experiment runner: evaluates a dataset x prompt versions x models matrix concurrently."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from evalplatform.db.models import (
    CaseResult,
    Experiment,
    ExperimentVariant,
    MetricScore,
    TestCase,
    Trace,
)
from evalplatform.logging import get_logger
from evalplatform.metrics.base import EvalSample, Metric
from evalplatform.metrics.registry import create_metric
from evalplatform.providers.base import CompletionRequest, CompletionResponse, ProviderError
from evalplatform.providers.pricing import get_pricing
from evalplatform.services.context import AppServices
from evalplatform.services.evaluation import case_passed, evaluate_sample
from evalplatform.services.prompts import PromptRenderError, build_variables, render
from evalplatform.services.stats import (
    ScorePoint,
    aggregate,
    composite_score,
    evaluate_gates,
    normalize_thresholds,
)
from evalplatform.services.traces import span_rows
from evalplatform.tracing import get_tracer

log = get_logger(__name__)

MAX_ATTEMPTS = 3


@dataclass(slots=True)
class CaseData:
    id: str
    input: str
    context: list[str]
    expected_output: str | None
    tags: list[str]
    metadata: dict[str, Any]


class ExperimentRunner:
    def __init__(self, services: AppServices) -> None:
        self.services = services
        self.db = services.db
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------ public
    async def run(self, experiment_id: str) -> None:
        try:
            await self._run(experiment_id)
        except asyncio.CancelledError:
            summary: dict[str, Any] | None = None
            try:
                summary = await self.build_summary(experiment_id)
            except Exception:  # pragma: no cover - best effort partial summary
                log.warning("experiment.partial_summary_failed", experiment_id=experiment_id)
            await self._finish(
                experiment_id, "cancelled", summary=summary, error="Cancelled by user"
            )
            raise
        except Exception as exc:
            log.exception("experiment.failed", experiment_id=experiment_id)
            await self._finish(experiment_id, "failed", error=f"{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ internals
    async def _run(self, experiment_id: str) -> None:
        async with self.db.sessionmaker() as session:
            exp = await session.get(
                Experiment, experiment_id, options=[selectinload(Experiment.variants)]
            )
            if exp is None:
                raise ValueError(f"Experiment {experiment_id} not found")
            stmt = (
                select(TestCase)
                .where(TestCase.dataset_id == exp.dataset_id)
                .order_by(TestCase.position)
            )
            if exp.case_limit:
                stmt = stmt.limit(exp.case_limit)
            cases = [
                CaseData(
                    c.id,
                    c.input,
                    list(c.context or []),
                    c.expected_output,
                    list(c.tags or []),
                    dict(c.metadata_ or {}),
                )
                for c in (await session.scalars(stmt)).all()
            ]
            variants = list(exp.variants)
            metric_specs = list(exp.metrics)
            concurrency = max(1, min(exp.concurrency, self.services.settings.max_concurrency))
            exp.status = "running"
            exp.started_at = datetime.now(UTC)
            exp.progress_total = len(cases) * len(variants)
            exp.progress_done = 0
            exp.progress_failed = 0
            await session.commit()

        metrics = [create_metric(spec) for spec in metric_specs]
        log.info(
            "experiment.started",
            experiment_id=experiment_id,
            cases=len(cases),
            variants=len(variants),
            metrics=len(metrics),
            concurrency=concurrency,
        )
        semaphore = asyncio.Semaphore(concurrency)

        async def worker(variant: ExperimentVariant, case: CaseData) -> None:
            async with semaphore:
                await self._run_case(experiment_id, variant, case, metrics)

        await asyncio.gather(*(worker(v, c) for v in variants for c in cases))
        summary = await self.build_summary(experiment_id)
        await self._finish(experiment_id, "completed", summary=summary)
        log.info(
            "experiment.completed",
            experiment_id=experiment_id,
            gate_passed=summary.get("gate_passed"),
        )

    async def _generate(
        self, variant: ExperimentVariant, system: str | None, user: str, case: CaseData
    ) -> CompletionResponse:
        m = variant.model_snapshot
        provider = self.services.providers.get(m["provider"])
        last_error: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            request = CompletionRequest(
                model=m["model"],
                system=system,
                user=user,
                temperature=m.get("temperature"),
                max_tokens=int(m.get("max_tokens") or 512),
                params=dict(m.get("params") or {}),
                hints={
                    "input": case.input,
                    "expected_output": case.expected_output,
                    "context": case.context,
                    "tags": case.tags,
                    "metadata": case.metadata,
                    "attempt": attempt,
                },
            )
            async with get_tracer().span(
                "llm.generate",
                kind="llm",
                provider=m["provider"],
                model=m["model"],
                attempt=attempt,
                **{"gen_ai.system": m["provider"], "gen_ai.request.model": m["model"]},
            ) as span:
                try:
                    response = await provider.complete(request)
                except ProviderError as exc:
                    last_error = exc
                    span.set("error", str(exc))
                    span.record.status = "error"
                    span.record.error = str(exc)
                    response = None
                if response is not None:
                    span.update(
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        latency_ms=round(response.latency_ms, 2),
                        ttft_ms=round(response.ttft_ms, 2)
                        if response.ttft_ms is not None
                        else None,
                        output=response.text[:2000],
                        **{
                            "gen_ai.usage.input_tokens": response.input_tokens,
                            "gen_ai.usage.output_tokens": response.output_tokens,
                        },
                    )
                    return response
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(0.2 * 2**attempt)
        raise ProviderError(f"Failed after {MAX_ATTEMPTS} attempts: {last_error}")

    async def _run_case(
        self, experiment_id: str, variant: ExperimentVariant, case: CaseData, metrics: list[Metric]
    ) -> None:
        tracer = get_tracer()
        p = variant.prompt_snapshot
        m = variant.model_snapshot
        result = CaseResult(
            experiment_id=experiment_id, variant_id=variant.id, test_case_id=case.id
        )
        scores: list[MetricScore] = []
        response: CompletionResponse | None = None
        system: str | None = None
        with tracer.trace(f"eval:{variant.label}") as collector:
            async with tracer.span(
                "experiment.case", kind="chain", variant=variant.label, test_case_id=case.id
            ) as root:
                try:
                    variables = build_variables(case.input, case.context, case.tags, case.metadata)
                    system = render(p.get("system_prompt") or "", variables) or None
                    user = render(p["user_template"], variables)
                    result.rendered_prompt = (
                        f"[system]\n{system}\n\n" if system else ""
                    ) + f"[user]\n{user}"
                    response = await self._generate(variant, system, user, case)
                except (PromptRenderError, ProviderError) as exc:
                    result.error = str(exc)
                    root.set("error", str(exc))
                if response is not None:
                    cost = get_pricing().cost(
                        m["model"], response.input_tokens, response.output_tokens, m["provider"]
                    )
                    result.output = response.text
                    result.latency_ms = response.latency_ms
                    result.ttft_ms = response.ttft_ms
                    result.input_tokens = response.input_tokens
                    result.output_tokens = response.output_tokens
                    result.cost_usd = cost
                    sample = EvalSample(
                        input=case.input,
                        output=response.text,
                        expected_output=case.expected_output,
                        context=case.context,
                        tags=case.tags,
                        metadata=case.metadata,
                        system_prompt=system,
                        model=m["model"],
                        provider=m["provider"],
                        latency_ms=response.latency_ms,
                        ttft_ms=response.ttft_ms,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        cost_usd=cost,
                    )
                    async with tracer.span("evaluate", kind="chain", metrics=len(metrics)):
                        scored = await evaluate_sample(
                            sample, metrics, self.services.metric_context()
                        )
                    result.passed = case_passed(scored)
                    for s in scored:
                        scores.append(
                            MetricScore(
                                metric=s.metric.name,
                                category=s.metric.category,
                                value=s.result.value,
                                passed=s.result.passed,
                                explanation=s.result.explanation,
                                details=s.result.details,
                                error=s.result.error,
                            )
                        )
                    root.set("passed", result.passed)
                else:
                    result.passed = False

        trace = Trace(
            id=collector.trace_id,
            name=collector.name,
            source="experiment",
            experiment_id=experiment_id,
            status="error" if result.error else "ok",
            input=case.input,
            output=result.output,
            context=case.context,
            provider=m["provider"],
            model=m["model"],
            latency_ms=result.latency_ms,
            ttft_ms=result.ttft_ms,
            input_tokens=result.input_tokens or 0,
            output_tokens=result.output_tokens or 0,
            cost_usd=result.cost_usd or 0.0,
            tags=case.tags,
            metadata_={"variant_id": variant.id, "test_case_id": case.id},
            score_status="done",
            start_time=collector.start_time,
            end_time=collector.end_time,
        )
        result.trace_id = trace.id
        result.scores = scores
        async with self._write_lock, self.db.sessionmaker() as session:
            session.add(trace)
            session.add_all(span_rows(collector.spans, trace.id))
            session.add(result)
            await session.execute(
                update(Experiment)
                .where(Experiment.id == experiment_id)
                .values(
                    progress_done=Experiment.progress_done + 1,
                    progress_failed=Experiment.progress_failed + (1 if result.error else 0),
                )
            )
            await session.commit()

    async def build_summary(self, experiment_id: str) -> dict[str, Any]:
        async with self.db.sessionmaker() as session:
            exp = await session.get(
                Experiment, experiment_id, options=[selectinload(Experiment.variants)]
            )
            assert exp is not None
            rows = (
                await session.execute(
                    select(
                        CaseResult.variant_id,
                        CaseResult.passed,
                        CaseResult.error,
                        CaseResult.cost_usd,
                        MetricScore.metric,
                        MetricScore.value,
                        MetricScore.passed,
                        CaseResult.id,
                    )
                    .outerjoin(MetricScore, MetricScore.case_result_id == CaseResult.id)
                    .where(CaseResult.experiment_id == experiment_id)
                )
            ).all()
            thresholds = normalize_thresholds(exp.thresholds)
            variants_out: list[dict[str, Any]] = []
            for variant in exp.variants:
                vrows = [r for r in rows if r[0] == variant.id]
                cases: dict[str, tuple[bool | None, str | None, float]] = {
                    r[7]: (r[1], r[2], r[3] or 0.0) for r in vrows
                }
                points = [ScorePoint(r[4], r[5], r[6]) for r in vrows if r[4] is not None]
                aggs = aggregate(points)
                judged = [c[0] for c in cases.values() if c[0] is not None]
                summary: dict[str, Any] = {
                    "variant_id": variant.id,
                    "label": variant.label,
                    "model": variant.model_snapshot.get("model"),
                    "provider": variant.model_snapshot.get("provider"),
                    "model_config_name": variant.model_snapshot.get("name"),
                    "prompt": variant.prompt_snapshot.get("name"),
                    "prompt_version": variant.prompt_snapshot.get("version"),
                    "cases": len(cases),
                    "errors": sum(1 for c in cases.values() if c[1]),
                    "pass_rate": round(sum(judged) / len(judged), 4) if judged else None,
                    "total_cost_usd": round(sum(c[2] for c in cases.values()), 6),
                    "composite_score": composite_score(aggs),
                    "metrics": aggs,
                }
                gates = evaluate_gates(summary, thresholds)
                summary["gates"] = gates
                summary["gate_passed"] = all(g["passed"] for g in gates) if gates else None
                variants_out.append(summary)
            ranked = sorted(
                variants_out,
                key=lambda v: (v["composite_score"] is None, -(v["composite_score"] or 0)),
            )
            for i, v in enumerate(ranked, start=1):
                v["rank"] = i
            gate_values = [v["gate_passed"] for v in variants_out if v["gate_passed"] is not None]
            return {
                "variants": ranked,
                "gate_passed": all(gate_values) if gate_values else None,
                "best_variant_id": ranked[0]["variant_id"] if ranked else None,
            }

    async def _finish(
        self,
        experiment_id: str,
        status: str,
        *,
        summary: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        async with self._write_lock, self.db.sessionmaker() as session:
            exp = await session.get(Experiment, experiment_id)
            if exp is None:
                return
            exp.status = status
            exp.finished_at = datetime.now(UTC)
            if summary is not None:
                exp.summary = summary
            if error is not None:
                exp.error = error
            await session.commit()
