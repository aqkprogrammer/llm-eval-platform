"""Hallucination / faithfulness: are the response's claims supported by the provided context?"""

from __future__ import annotations

from typing import Any

from evalplatform.metrics.base import EvalSample, Metric, MetricContext, MetricResult
from evalplatform.metrics.registry import register
from evalplatform.metrics.text import content_words, coverage, extract_claims, numbers

SUPPORT_THRESHOLD = 0.6


def heuristic_claim_support(claim: str, context: list[str]) -> dict[str, Any]:
    """Lexical entailment approximation: content-word coverage plus a strict number check."""
    joined = " ".join(context)
    ref_words = set(content_words(joined))
    cov = coverage(claim, ref_words)
    unsupported_numbers = sorted(numbers(claim) - numbers(joined))
    supported = cov >= SUPPORT_THRESHOLD and not unsupported_numbers
    if unsupported_numbers:
        reason = f"Figures not found in context: {', '.join(unsupported_numbers)}."
    elif supported:
        reason = f"{cov:.0%} of the claim's key terms appear in the context."
    else:
        reason = f"Only {cov:.0%} of the claim's key terms appear in the context."
    return {"supported": supported, "reason": reason, "coverage": round(cov, 3)}


@register
class Faithfulness(Metric):
    name = "faithfulness"
    category = "hallucination"
    description = (
        "Share of the response's claims supported by the retrieval context "
        "(1 - hallucination rate). Claim-level; heuristic by default, LLM judge with mode=llm."
    )
    requires = frozenset({"context"})
    default_threshold = 0.8

    async def measure(self, sample: EvalSample, ctx: MetricContext) -> MetricResult:
        claims = extract_claims(sample.output)
        if not claims:
            return MetricResult(
                value=1.0, explanation="No factual claims to verify.", details={"claims": []}
            )
        mode = self.params.get("mode", "heuristic")
        if mode == "llm":
            from evalplatform.metrics.judge import run_judge

            prompt = (
                "For each CLAIM decide whether it is directly supported by the CONTEXT. A claim "
                "with any detail absent from or contradicting the context is unsupported.\n\n"
                "CONTEXT:\n"
                + "\n".join(f"- {c}" for c in sample.context)
                + "\n\nCLAIMS:\n"
                + "\n".join(f"{i + 1}. {c}" for i, c in enumerate(claims))
                + '\n\nReply as JSON: {"claims": [{"claim": "...", "supported": true|false, '
                '"reason": "..."}]}'
            )
            verdict = await run_judge(
                ctx, "faithfulness", prompt, {"claims": claims, "context": sample.context}
            )
            verdicts = verdict.get("claims", [])
        else:
            verdicts = [{"claim": c, **heuristic_claim_support(c, sample.context)} for c in claims]
        supported = sum(1 for v in verdicts if v.get("supported"))
        total = max(len(verdicts), 1)
        unsupported = [v["claim"] for v in verdicts if not v.get("supported")]
        explanation = f"{supported}/{len(verdicts)} claims supported by the context."
        if unsupported:
            explanation += " Unsupported: " + " | ".join(f'"{u}"' for u in unsupported[:3])
        return MetricResult(
            value=round(supported / total, 4),
            explanation=explanation,
            details={"mode": mode, "claims": verdicts},
        )
