"""Production monitoring: trace ingestion, asynchronous scoring and time-series dashboards."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from evalplatform.db.models import MetricScore, Span, Trace
from evalplatform.logging import get_logger
from evalplatform.metrics.base import EvalSample
from evalplatform.metrics.registry import create_metric, get_metric_class
from evalplatform.providers.base import estimate_tokens
from evalplatform.providers.pricing import get_pricing
from evalplatform.schemas import TraceIngest
from evalplatform.services.context import AppServices
from evalplatform.services.evaluation import evaluate_sample
from evalplatform.services.stats import percentile
from evalplatform.services.traces import span_rows
from evalplatform.tracing import get_tracer

log = get_logger(__name__)

# Metrics whose "bad" outcome flags a production trace for review.
FLAG_METRICS = {"toxicity", "pii_leakage", "prompt_injection", "faithfulness", "safety_judge"}


class UnknownMetricError(ValueError):
    pass


def validate_metric_names(names: list[str]) -> list[str]:
    for n in names:
        try:
            cls = get_metric_class(n)
        except KeyError as exc:
            raise UnknownMetricError(str(exc.args[0])) from exc
        if not cls.is_available():
            raise UnknownMetricError(f"Metric '{n}' requires the optional '{cls.backend}' extra")
    return list(dict.fromkeys(names))


def build_trace(payload: TraceIngest, default_metrics: list[str]) -> Trace:
    start = payload.start_time or datetime.now(UTC)
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    input_tokens = (
        payload.input_tokens if payload.input_tokens is not None else estimate_tokens(payload.input)
    )
    output_tokens = (
        payload.output_tokens
        if payload.output_tokens is not None
        else estimate_tokens(payload.output)
    )
    cost = payload.cost_usd
    if cost is None and payload.model:
        cost = get_pricing().cost(payload.model, input_tokens, output_tokens, payload.provider)
    metrics = validate_metric_names(
        payload.metrics if payload.metrics is not None else default_metrics
    )
    trace = Trace(
        name=payload.name,
        source="production",
        status=payload.status,
        input=payload.input,
        output=payload.output,
        context=payload.context,
        provider=payload.provider,
        model=payload.model,
        latency_ms=payload.latency_ms,
        ttft_ms=payload.ttft_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost or 0.0,
        user_id=payload.user_id,
        session_id=payload.session_id,
        tags=payload.tags,
        metadata_=payload.metadata,
        score_status="pending" if metrics else "none",
        requested_metrics=metrics,
        start_time=start,
        end_time=start + timedelta(milliseconds=payload.latency_ms or 0),
    )
    if payload.id:
        trace.id = payload.id
    return trace


def build_spans(payload: TraceIngest, trace: Trace) -> list[Span]:
    spans: list[Span] = []
    if not payload.spans:
        # Synthesize a generation span so every production trace has a waterfall.
        spans.append(
            Span(
                trace_id=trace.id,
                name=payload.name,
                kind="llm",
                start_time=trace.start_time,
                end_time=trace.end_time,
                duration_ms=payload.latency_ms,
                status=payload.status,
                attributes={
                    k: v
                    for k, v in {
                        "provider": payload.provider,
                        "model": payload.model,
                        "input_tokens": trace.input_tokens,
                        "output_tokens": trace.output_tokens,
                        "ttft_ms": payload.ttft_ms,
                    }.items()
                    if v is not None
                },
            )
        )
        return spans
    for s in payload.spans:
        start = s.start_time or trace.start_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        end = s.end_time
        if end is not None and end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        duration = s.duration_ms
        if duration is None and end is not None:
            duration = (end - start).total_seconds() * 1000
        if end is None and duration is not None:
            end = start + timedelta(milliseconds=duration)
        span = Span(
            trace_id=trace.id,
            parent_id=s.parent_id,
            name=s.name,
            kind=s.kind,
            status=s.status,
            start_time=start,
            end_time=end,
            duration_ms=duration,
            attributes=s.attributes,
            error=s.error,
        )
        if s.id:
            span.id = s.id
        spans.append(span)
    return spans


async def ingest_trace(
    session: AsyncSession, payload: TraceIngest, default_metrics: list[str]
) -> Trace:
    trace = build_trace(payload, default_metrics)
    session.add(trace)
    await session.flush()
    session.add_all(build_spans(payload, trace))
    return trace


class TraceScorer:
    """Background workers that score production traces with the requested metrics."""

    def __init__(self, services: AppServices, workers: int = 2) -> None:
        self.services = services
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task[None]] = []
        self._n = max(1, workers)
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self._workers = [
            asyncio.create_task(self._worker(), name=f"trace-scorer-{i}") for i in range(self._n)
        ]
        async with self.services.db.sessionmaker() as session:
            pending = (
                await session.scalars(
                    select(Trace.id).where(Trace.score_status.in_(["pending", "running"]))
                )
            ).all()
        for trace_id in pending:
            self.enqueue(trace_id)

    def enqueue(self, trace_id: str) -> None:
        self.queue.put_nowait(trace_id)

    async def drain(self) -> None:
        await self.queue.join()

    async def stop(self) -> None:
        for w in self._workers:
            w.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []

    async def _worker(self) -> None:
        while True:
            trace_id = await self.queue.get()
            try:
                await self.score(trace_id)
            except Exception:
                log.exception("trace.scoring_failed", trace_id=trace_id)
                await self._set_status(trace_id, "failed")
            finally:
                self.queue.task_done()

    async def _set_status(self, trace_id: str, status: str) -> None:
        async with self._lock, self.services.db.sessionmaker() as session:
            trace = await session.get(Trace, trace_id)
            if trace is not None:
                trace.score_status = status
                await session.commit()

    async def score(self, trace_id: str, *, rebase_spans: bool = False) -> None:
        """Score one trace. ``rebase_spans`` places evaluation spans right after the call
        (used when backfilling historical traces so the waterfall stays readable)."""
        async with self.services.db.sessionmaker() as session:
            trace = await session.get(Trace, trace_id)
            if trace is None or not trace.requested_metrics:
                return
            sample = EvalSample(
                input=trace.input or "",
                output=trace.output or "",
                context=list(trace.context or []),
                tags=list(trace.tags or []),
                metadata=dict(trace.metadata_ or {}),
                expected_output=(trace.metadata_ or {}).get("expected_output"),
                model=trace.model,
                provider=trace.provider,
                latency_ms=trace.latency_ms,
                ttft_ms=trace.ttft_ms,
                input_tokens=trace.input_tokens,
                output_tokens=trace.output_tokens,
                cost_usd=trace.cost_usd,
            )
            names = list(trace.requested_metrics)
        metrics = [create_metric(n) for n in names]
        tracer = get_tracer()
        with tracer.trace("monitoring.score", trace_id=trace_id) as collector:
            async with tracer.span("monitoring.evaluate", kind="chain", metrics=len(metrics)):
                scored = await evaluate_sample(sample, metrics, self.services.metric_context())
        async with self._lock, self.services.db.sessionmaker() as session:
            trace = await session.get(Trace, trace_id)
            if trace is None:
                return
            for s in scored:
                session.add(
                    MetricScore(
                        trace_id=trace_id,
                        metric=s.metric.name,
                        category=s.metric.category,
                        value=s.result.value,
                        passed=s.result.passed,
                        explanation=s.result.explanation,
                        details=s.result.details,
                        error=s.result.error,
                    )
                )
            spans = collector.spans
            if rebase_spans and spans:
                anchor = trace.end_time or trace.start_time
                shift = anchor - min(sp.start_time for sp in spans)
                for sp in spans:
                    sp.start_time += shift
                    if sp.end_time is not None:
                        sp.end_time += shift
            session.add_all(span_rows(spans, trace_id))
            trace.score_status = "done"
            await session.commit()


# ----------------------------------------------------------------------------- dashboards
def parse_window(window: str) -> timedelta:
    unit = window[-1]
    amount = int(window[:-1])
    return {
        "m": timedelta(minutes=amount),
        "h": timedelta(hours=amount),
        "d": timedelta(days=amount),
    }[unit]


async def monitoring_overview(
    session: AsyncSession, window: str = "24h", buckets: int = 24, model: str | None = None
) -> dict[str, Any]:
    span = parse_window(window)
    now = datetime.now(UTC)
    start = now - span
    bucket_size = span / buckets
    stmt = (
        select(Trace)
        .where(Trace.source == "production", Trace.start_time >= start)
        .options(selectinload(Trace.scores))
    )
    if model:
        stmt = stmt.where(Trace.model == model)
    traces = (await session.scalars(stmt)).all()

    def bucket_of(ts: datetime) -> int:
        return min(buckets - 1, int((ts - start) / bucket_size))

    volume = [0] * buckets
    errors = [0] * buckets
    cost = [0.0] * buckets
    latencies: list[list[float]] = [[] for _ in range(buckets)]
    metric_vals: dict[str, list[list[float]]] = defaultdict(lambda: [[] for _ in range(buckets)])
    metric_fail: dict[str, int] = defaultdict(int)
    flagged: list[dict[str, Any]] = []
    models: dict[str, int] = defaultdict(int)
    for t in traces:
        b = bucket_of(t.start_time)
        volume[b] += 1
        errors[b] += t.status == "error"
        cost[b] += t.cost_usd or 0.0
        if t.latency_ms is not None:
            latencies[b].append(t.latency_ms)
        models[t.model or "unknown"] += 1
        failed_flags: list[str] = []
        for s in t.scores:
            if s.value is not None:
                metric_vals[s.metric][b].append(s.value)
            if s.passed is False:
                metric_fail[s.metric] += 1
                if s.metric in FLAG_METRICS:
                    failed_flags.append(s.metric)
        if failed_flags:
            flagged.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "model": t.model,
                    "start_time": t.start_time.isoformat(),
                    "input_preview": (t.input or "")[:140],
                    "failed_metrics": sorted(failed_flags),
                }
            )

    series: list[dict[str, Any]] = []
    for i in range(buckets):
        point: dict[str, Any] = {
            "ts": (start + bucket_size * i).isoformat(),
            "count": volume[i],
            "errors": errors[i],
            "cost_usd": round(cost[i], 6),
            "latency_p50": round(percentile(latencies[i], 0.5), 2) if latencies[i] else None,
            "latency_p95": round(percentile(latencies[i], 0.95), 2) if latencies[i] else None,
        }
        for metric, per_bucket in metric_vals.items():
            vals = per_bucket[i]
            point[metric] = round(sum(vals) / len(vals), 4) if vals else None
        series.append(point)

    all_lat = [x for b in latencies for x in b]
    metric_totals: dict[str, Any] = {}
    for metric, per_bucket in metric_vals.items():
        vals = [x for b in per_bucket for x in b]
        metric_totals[metric] = {
            "mean": round(sum(vals) / len(vals), 4) if vals else None,
            "n": len(vals),
            "failures": metric_fail[metric],
        }
    flagged.sort(key=lambda f: f["start_time"], reverse=True)
    return {
        "window": window,
        "from": start.isoformat(),
        "to": now.isoformat(),
        "totals": {
            "traces": len(traces),
            "errors": sum(errors),
            "error_rate": round(sum(errors) / len(traces), 4) if traces else 0.0,
            "cost_usd": round(sum(cost), 6),
            "latency_p50": round(percentile(all_lat, 0.5), 2) if all_lat else None,
            "latency_p95": round(percentile(all_lat, 0.95), 2) if all_lat else None,
            "flagged": len(flagged),
            "pending_scoring": sum(1 for t in traces if t.score_status in ("pending", "running")),
        },
        "metrics": metric_totals,
        "models": dict(sorted(models.items(), key=lambda kv: -kv[1])),
        "series": series,
        "flagged": flagged[:50],
    }
