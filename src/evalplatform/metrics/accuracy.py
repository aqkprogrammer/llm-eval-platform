"""Reference-based accuracy metrics."""

from __future__ import annotations

from rapidfuzz import fuzz

from evalplatform.metrics.base import EvalSample, Metric, MetricContext, MetricResult
from evalplatform.metrics.embeddings import LexicalEmbedder
from evalplatform.metrics.registry import register
from evalplatform.metrics.text import normalize, numbers


@register
class ExactMatch(Metric):
    name = "exact_match"
    category = "accuracy"
    description = (
        "1 if the normalised response equals the reference (case/punctuation-insensitive)."
    )
    requires = frozenset({"expected_output"})
    default_threshold = 1.0

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        assert sample.expected_output is not None
        out, exp = normalize(sample.output), normalize(sample.expected_output)
        match = out == exp
        return MetricResult(
            value=1.0 if match else 0.0,
            explanation="Response exactly matches the reference."
            if match
            else "Response differs from the reference after normalisation.",
        )


@register
class FuzzyMatch(Metric):
    name = "fuzzy_match"
    category = "accuracy"
    description = (
        "Token-set fuzzy ratio between response and reference (tolerates reordering and extra "
        "words); numbers in the reference must also appear in the response."
    )
    requires = frozenset({"expected_output"})
    default_threshold = 0.8

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        assert sample.expected_output is not None
        ratio = fuzz.token_set_ratio(normalize(sample.output), normalize(sample.expected_output))
        score = ratio / 100
        missing = numbers(sample.expected_output) - numbers(sample.output)
        if missing:
            score = min(score, 0.5)
        explanation = f"Token-set similarity {ratio:.0f}/100."
        if missing:
            explanation += (
                f" Reference numbers missing from response: {', '.join(sorted(missing))}."
            )
        return MetricResult(
            value=round(score, 4),
            explanation=explanation,
            details={"missing_numbers": sorted(missing)},
        )


@register
class SemanticSimilarity(Metric):
    name = "semantic_similarity"
    category = "accuracy"
    description = (
        "Embedding cosine similarity between response and reference (lexical embeddings offline, "
        "OpenAI embeddings when EMBEDDING_PROVIDER=openai)."
    )
    requires = frozenset({"expected_output"})
    default_threshold = 0.7

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        assert sample.expected_output is not None
        embedder = ctx.embedder or LexicalEmbedder()
        sim = await embedder.similarity(sample.output, sample.expected_output)
        return MetricResult(
            value=round(sim, 4),
            explanation=f"Cosine similarity {sim:.2f} using the '{embedder.name}' embedder.",
            details={"embedder": embedder.name},
        )
