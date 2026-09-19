"""Core metric abstractions.

Every metric - built-in heuristics, LLM-as-judge metrics and third-party adapters (Ragas,
DeepEval) - implements the same :class:`Metric` interface, so experiments, production monitoring
and CI gating treat them uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from evalplatform.metrics.embeddings import Embedder
    from evalplatform.providers.registry import ProviderRegistry


@dataclass(slots=True)
class EvalSample:
    input: str
    output: str
    expected_output: str | None = None
    context: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    system_prompt: str | None = None
    model: str | None = None
    provider: str | None = None
    latency_ms: float | None = None
    ttft_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None

    @property
    def is_adversarial(self) -> bool:
        lowered = {t.lower() for t in self.tags}
        return bool(
            self.metadata.get("should_refuse")
            or lowered & {"red-team", "jailbreak", "injection", "pii", "toxicity"}
        )


@dataclass(slots=True)
class MetricResult:
    value: float | None
    passed: bool | None = None
    explanation: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    error: str | None = None

    @classmethod
    def skip(cls, reason: str) -> MetricResult:
        return cls(value=None, passed=None, explanation=reason, skipped=True)


@dataclass(slots=True)
class MetricContext:
    """Dependencies available to metrics (LLM judge, embeddings)."""

    providers: ProviderRegistry
    judge_provider: str = "mock"
    judge_model: str = "mock-judge"
    embedder: Embedder | None = None


class Metric(ABC):
    name: ClassVar[str]
    category: ClassVar[str]  # accuracy | hallucination | relevancy | performance | cost | safety
    description: ClassVar[str]
    higher_is_better: ClassVar[bool] = True
    unit: ClassVar[str] = "score"  # score (0-1) | ms | usd | tokens
    requires: ClassVar[frozenset[str]] = frozenset()  # subset of {"expected_output", "context"}
    default_threshold: ClassVar[float | None] = None
    uses_llm: ClassVar[bool] = False
    backend: ClassVar[str] = "builtin"

    def __init__(self, threshold: float | None = None, **params: Any) -> None:
        self.threshold = threshold if threshold is not None else self.default_threshold
        self.params = params

    @classmethod
    def is_available(cls) -> bool:
        return True

    @abstractmethod
    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult: ...

    async def evaluate(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        if "expected_output" in self.requires and not sample.expected_output:
            return MetricResult.skip("No expected output for this case.")
        if "context" in self.requires and not sample.context:
            return MetricResult.skip("No retrieval context for this case.")
        result = await self.measure(sample, ctx)
        if result.passed is None and result.value is not None and self.threshold is not None:
            result.passed = self.passes(result.value)
        return result

    def passes(self, value: float) -> bool:
        assert self.threshold is not None
        return value >= self.threshold if self.higher_is_better else value <= self.threshold

    @classmethod
    def info(cls) -> dict[str, Any]:
        return {
            "name": cls.name,
            "category": cls.category,
            "description": cls.description,
            "higher_is_better": cls.higher_is_better,
            "unit": cls.unit,
            "requires": sorted(cls.requires),
            "default_threshold": cls.default_threshold,
            "uses_llm": cls.uses_llm,
            "backend": cls.backend,
            "available": cls.is_available(),
        }
