"""Operational metrics: latency, time-to-first-token, token usage and cost."""

from __future__ import annotations

from evalplatform.metrics.base import EvalSample, Metric, MetricContext, MetricResult
from evalplatform.metrics.registry import register


@register
class Latency(Metric):
    name = "latency_ms"
    category = "performance"
    description = "End-to-end generation latency in milliseconds."
    higher_is_better = False
    unit = "ms"
    default_threshold = 3000.0

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        if sample.latency_ms is None:
            return MetricResult.skip("Latency not recorded.")
        return MetricResult(
            value=round(sample.latency_ms, 2), explanation=f"{sample.latency_ms:.0f} ms total."
        )


@register
class TimeToFirstToken(Metric):
    name = "ttft_ms"
    category = "performance"
    description = "Time to first streamed token in milliseconds (perceived responsiveness)."
    higher_is_better = False
    unit = "ms"
    default_threshold = 1000.0

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        if sample.ttft_ms is None:
            return MetricResult.skip("TTFT not recorded (non-streaming call).")
        return MetricResult(
            value=round(sample.ttft_ms, 2),
            explanation=f"First token after {sample.ttft_ms:.0f} ms.",
        )


@register
class TotalTokens(Metric):
    name = "total_tokens"
    category = "cost"
    description = "Prompt + completion tokens."
    higher_is_better = False
    unit = "tokens"

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        total = sample.input_tokens + sample.output_tokens
        return MetricResult(
            value=float(total),
            explanation=f"{sample.input_tokens} prompt + {sample.output_tokens} completion tokens.",
            details={"input_tokens": sample.input_tokens, "output_tokens": sample.output_tokens},
        )


@register
class Cost(Metric):
    name = "cost_usd"
    category = "cost"
    description = "Request cost in USD from the per-model pricing table."
    higher_is_better = False
    unit = "usd"

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        cost = sample.cost_usd
        if cost is None:
            from evalplatform.providers.pricing import get_pricing

            cost = get_pricing().cost(
                sample.model or "", sample.input_tokens, sample.output_tokens, sample.provider
            )
        return MetricResult(value=round(cost, 8), explanation=f"${cost:.6f} for this call.")
