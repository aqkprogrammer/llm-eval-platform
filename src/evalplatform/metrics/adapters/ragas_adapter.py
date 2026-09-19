"""Ragas adapter (optional extra: ``uv sync --extra ragas``).

Ragas metrics need an evaluator LLM; we build one from the configured OpenAI key via
``ragas.llms.llm_factory``. Metrics are registered unconditionally and report
``available = False`` when Ragas is not installed so the UI can explain why.
"""

from __future__ import annotations

import importlib.util
from typing import Any, ClassVar

from evalplatform.metrics.base import EvalSample, Metric, MetricContext, MetricResult
from evalplatform.metrics.registry import register


class _RagasMetric(Metric):
    backend = "ragas"
    uses_llm = True
    ragas_class: ClassVar[str]

    @classmethod
    def is_available(cls) -> bool:
        return importlib.util.find_spec("ragas") is not None

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        import ragas.metrics as rm
        from ragas import SingleTurnSample
        from ragas.llms import llm_factory

        metric_cls: Any = getattr(rm, self.ragas_class)
        llm = llm_factory(self.params.get("model", "gpt-4o-mini"))
        metric = metric_cls(llm=llm)
        rs = SingleTurnSample(
            user_input=sample.input,
            response=sample.output,
            retrieved_contexts=sample.context or None,
            reference=sample.expected_output,
        )
        score = float(await metric.single_turn_ascore(rs))
        return MetricResult(
            value=round(score, 4), explanation=f"Ragas {self.ragas_class}: {score:.2f}"
        )


@register
class RagasFaithfulness(_RagasMetric):
    name = "ragas_faithfulness"
    category = "hallucination"
    description = "Ragas Faithfulness (LLM-extracted claims verified against context)."
    requires = frozenset({"context"})
    default_threshold = 0.8
    ragas_class = "Faithfulness"


@register
class RagasAnswerRelevancy(_RagasMetric):
    name = "ragas_answer_relevancy"
    category = "relevancy"
    description = "Ragas ResponseRelevancy (reverse-generated questions vs. the original)."
    default_threshold = 0.7
    ragas_class = "ResponseRelevancy"
