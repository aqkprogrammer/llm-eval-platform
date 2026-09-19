"""Shared evaluation engine: run a set of metrics over one sample, each inside its own span."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from evalplatform.logging import get_logger
from evalplatform.metrics.base import EvalSample, Metric, MetricContext, MetricResult
from evalplatform.tracing import get_tracer

log = get_logger(__name__)


@dataclass(slots=True)
class ScoredMetric:
    metric: Metric
    result: MetricResult


async def _evaluate_one(metric: Metric, sample: EvalSample, ctx: MetricContext) -> ScoredMetric:
    async with get_tracer().span(
        f"metric.{metric.name}", kind="metric", metric=metric.name, category=metric.category
    ) as span:
        try:
            result = await metric.evaluate(sample, ctx)
        except Exception as exc:  # a broken metric must never break the run
            log.warning("metric.failed", metric=metric.name, error=str(exc))
            result = MetricResult(
                value=None, explanation="Metric evaluation failed.", error=str(exc)
            )
            span.set("error", str(exc))
        span.update(value=result.value, passed=result.passed, skipped=result.skipped)
    return ScoredMetric(metric, result)


async def evaluate_sample(
    sample: EvalSample, metrics: list[Metric], ctx: MetricContext
) -> list[ScoredMetric]:
    return list(await asyncio.gather(*(_evaluate_one(m, sample, ctx) for m in metrics)))


def case_passed(scored: list[ScoredMetric]) -> bool | None:
    verdicts = [s.result.passed for s in scored if s.result.passed is not None]
    return all(verdicts) if verdicts else None
