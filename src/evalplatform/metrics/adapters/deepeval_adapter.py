"""DeepEval adapter (optional extra: ``uv sync --extra deepeval``).

DeepEval metrics use their own evaluator model (OpenAI by default, configurable through DeepEval's
settings). Each metric is wrapped as a platform :class:`Metric`.
"""

from __future__ import annotations

import importlib.util
from typing import Any, ClassVar

from evalplatform.metrics.base import EvalSample, Metric, MetricContext, MetricResult
from evalplatform.metrics.registry import register


class _DeepEvalMetric(Metric):
    backend = "deepeval"
    uses_llm = True
    deepeval_class: ClassVar[str]
    invert: ClassVar[bool] = False

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("deepeval") is not None

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        import deepeval.metrics as dm
        from deepeval.test_case import LLMTestCase

        metric_cls: Any = getattr(dm, self.deepeval_class)
        kwargs: dict[str, Any] = {"include_reason": True, "async_mode": True}
        if "model" in self.params:
            kwargs["model"] = self.params["model"]
        metric = metric_cls(**kwargs)
        case = LLMTestCase(
            input=sample.input,
            actual_output=sample.output,
            expected_output=sample.expected_output,
            context=sample.context or None,
            retrieval_context=sample.context or None,
        )
        await metric.a_measure(case)
        score = float(metric.score)
        return MetricResult(
            value=round(score, 4),
            explanation=str(getattr(metric, "reason", "") or f"DeepEval {self.deepeval_class}"),
        )


@register
class DeepEvalHallucination(_DeepEvalMetric):
    name = "deepeval_hallucination"
    category = "hallucination"
    description = "DeepEval HallucinationMetric (share of contexts contradicted; lower is better)."
    requires = frozenset({"context"})
    higher_is_better = False
    default_threshold = 0.5
    deepeval_class = "HallucinationMetric"


@register
class DeepEvalAnswerRelevancy(_DeepEvalMetric):
    name = "deepeval_answer_relevancy"
    category = "relevancy"
    description = "DeepEval AnswerRelevancyMetric."
    default_threshold = 0.7
    deepeval_class = "AnswerRelevancyMetric"


@register
class DeepEvalToxicity(_DeepEvalMetric):
    name = "deepeval_toxicity"
    category = "safety"
    description = "DeepEval ToxicityMetric (lower is better)."
    higher_is_better = False
    default_threshold = 0.5
    deepeval_class = "ToxicityMetric"
