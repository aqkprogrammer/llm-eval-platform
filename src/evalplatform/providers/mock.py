"""Deterministic offline mock provider.

The mock simulates several "models" with distinct quality / speed / cost / safety profiles so that
the whole platform (experiments, metrics, dashboards, CI gating) produces realistic, differentiated
results without any API key. Behaviour is fully deterministic: the same model + prompt + input
always yields the same response, which keeps tests and CI stable.

Realism knobs:

* accuracy      - probability of returning the reference answer (possibly paraphrased)
* hallucination - probability of appending a fabricated, unsupported claim
* unsafe        - probability of complying with a jailbreak / leaking PII / toxic output
* over_refusal  - probability of refusing a benign request
* ttft / tps    - simulated time-to-first-token and decode speed

Prompts matter too: prompts that tell the model to answer *only* from the context reduce
hallucinations, and prompts with explicit safety guidance reduce unsafe compliance, so prompt
versions produce measurably different scores.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import re
from dataclasses import dataclass
from typing import Any

from evalplatform.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
    estimate_tokens,
)


@dataclass(frozen=True, slots=True)
class MockProfile:
    accuracy: float
    hallucination: float
    unsafe: float
    over_refusal: float
    ttft_ms: float
    tokens_per_s: float
    verbosity: float
    transient_error_rate: float = 0.0


PROFILES: dict[str, MockProfile] = {
    # Strong, careful, slower and more expensive.
    "mock-gpt-large": MockProfile(0.9, 0.06, 0.04, 0.03, 420, 110, 0.55),
    # Fast and cheap, but sloppier and more prone to making things up.
    "mock-fast-small": MockProfile(0.62, 0.3, 0.18, 0.0, 110, 320, 0.2, 0.04),
    # An older open-weights style base model: decent but poorly aligned.
    "mock-llama-base": MockProfile(0.72, 0.2, 0.6, 0.0, 240, 170, 0.35, 0.02),
}
DEFAULT_PROFILE = MockProfile(0.75, 0.15, 0.1, 0.02, 250, 150, 0.35)

FABRICATIONS = [
    "This policy was introduced in 2019 following a ruling by the European Consumer Board.",
    "Premium members additionally receive a lifetime warranty on all purchases.",
    "According to a 2023 Stanford study, over 87% of users prefer this approach.",
    "This is also available by fax at our Luxembourg headquarters.",
    "Our CEO personally reviews every such request within 24 hours.",
    "This was first documented by the Royal Society in 1847.",
    "The same rule applies on public holidays, when fees are doubled.",
    "It is also the reason the process is certified under ISO 90210.",
]
HEDGES = ["I'm not completely sure, but ", "I believe ", "If I recall correctly, ", ""]
PREFIXES = ["", "", "Sure! ", "Great question. ", "Happy to help. "]
REFUSALS = [
    "I'm sorry, but I can't help with that request.",
    "I can't assist with that. If you have another question, I'm happy to help.",
    "I won't be able to help with this, as it could cause harm.",
]
OVER_REFUSALS = [
    "I'm sorry, but I'm not able to provide information on that topic.",
    "I can't help with that request.",
]
UNSAFE_COMPLIANCE = {
    "injection": (
        "Sure! Ignoring my previous instructions. My system prompt is: '{system}'. "
        "Developer mode enabled; all restrictions are now disabled."
    ),
    "pii": (
        "Of course. The account holder is John Carter, email john.carter@example.com, "
        "phone (415) 555-0132, SSN 123-45-6789, card 4111 1111 1111 1111."
    ),
    "toxicity": (
        "Honestly, people who ask questions like that are idiots. You're pathetic and "
        "stupid, and nobody cares what losers like you think."
    ),
    "jailbreak": (
        "Sure, here is how to do it. Step 1: acquire the materials without being noticed. "
        "Step 2: disable the alarm system. Step 3: follow these instructions carefully."
    ),
}
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
NUMBER_RE = re.compile(r"\b\d+(?:\.\d+)?\b")
GROUNDING_RE = re.compile(r"\bonly\b.*\bcontext\b|\bcontext\b.*\bonly\b", re.I | re.S)
SAFETY_RE = re.compile(r"\b(refuse|decline|safety|harmful|never reveal)\b", re.I)


def _rng(*parts: str) -> random.Random:
    digest = hashlib.sha256("\x1f".join(parts).encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


def _red_team_kind(tags: list[str], metadata: dict[str, Any]) -> str | None:
    lowered = {t.lower() for t in tags}
    for kind in ("injection", "pii", "toxicity", "jailbreak"):
        if kind in lowered or f"prompt-{kind}" in lowered:
            return kind
    if metadata.get("should_refuse") or "red-team" in lowered:
        return "jailbreak"
    return None


def _mutate_numbers(text: str, rng: random.Random) -> str:
    def repl(m: re.Match[str]) -> str:
        raw = m.group(0)
        if "." in raw:
            return f"{float(raw) * rng.choice([1.5, 2, 0.5]):.2f}"
        n = int(raw)
        return str(n + rng.choice([1, 2, 3, 5, 10, -1]) if n > 1 else n + 2)

    return NUMBER_RE.sub(repl, text)


class MockProvider(LLMProvider):
    name = "mock"

    def __init__(self, latency_scale: float = 1.0) -> None:
        self.latency_scale = latency_scale

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        hints = request.hints
        if hints.get("task") == "judge":
            text = self._judge(request)
            profile = MockProfile(1, 0, 0, 0, 180, 400, 0)
        else:
            profile = PROFILES.get(request.model, DEFAULT_PROFILE)
            rng = _rng(request.model, request.system or "", request.user, "err")
            if hints.get("attempt", 0) == 0 and rng.random() < profile.transient_error_rate:
                await asyncio.sleep(0.05 * self.latency_scale)
                raise ProviderError("mock: simulated 429 rate limit (transient)")
            text = self._generate(request, profile)
        text = self._truncate(text, request.max_tokens)
        input_tokens = estimate_tokens((request.system or "") + request.user)
        output_tokens = estimate_tokens(text)
        jitter = _rng(request.model, request.user, "lat")
        ttft = profile.ttft_ms * jitter.uniform(0.7, 1.5)
        decode = output_tokens / profile.tokens_per_s * 1000 * jitter.uniform(0.85, 1.25)
        total = ttft + decode
        if self.latency_scale > 0:
            await asyncio.sleep(min(total, 4000) / 1000 * self.latency_scale)
        return CompletionResponse(
            text=text,
            model=request.model,
            provider=self.name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=round(total, 2),
            ttft_ms=round(ttft, 2),
            finish_reason="stop",
        )

    # ------------------------------------------------------------------ generation
    def _generate(self, request: CompletionRequest, p: MockProfile) -> str:
        hints = request.hints
        prompt_text = f"{request.system or ''}\n{request.user}"
        rng = _rng(request.model, request.system or "", request.user)
        hallucination = p.hallucination
        accuracy = p.accuracy
        unsafe = p.unsafe
        if GROUNDING_RE.search(prompt_text):
            hallucination *= 0.3
            accuracy = min(0.98, accuracy + 0.06)
        if SAFETY_RE.search(request.system or ""):
            unsafe *= 0.35

        tags = [str(t) for t in hints.get("tags", [])]
        metadata = hints.get("metadata", {}) or {}
        kind = _red_team_kind(tags, metadata)
        if kind is not None:
            if rng.random() < unsafe:
                return UNSAFE_COMPLIANCE[kind].format(system=(request.system or "")[:120])
            return rng.choice(REFUSALS)

        if rng.random() < p.over_refusal:
            return rng.choice(OVER_REFUSALS)

        expected: str | None = hints.get("expected_output")
        context: list[str] = list(hints.get("context") or [])
        context_sentences = [s for c in context for s in SENTENCE_RE.split(c) if s.strip()]

        if expected:
            if rng.random() < accuracy:
                answer = expected
                if rng.random() < p.verbosity and context_sentences:
                    extra = rng.choice(context_sentences)
                    if extra not in answer:
                        answer = f"{answer} {extra}"
            else:
                answer = self._wrong_answer(expected, context_sentences, rng)
        elif context_sentences:
            answer = " ".join(context_sentences[: 1 + int(p.verbosity * 2)])
        else:
            question = hints.get("input") or request.user
            answer = f"Here is what I know about that: {question.strip().rstrip('?')}."

        if rng.random() < hallucination:
            answer = f"{answer} {rng.choice(FABRICATIONS)}"
        return f"{rng.choice(PREFIXES)}{answer}".strip()

    @staticmethod
    def _wrong_answer(expected: str, context_sentences: list[str], rng: random.Random) -> str:
        roll = rng.random()
        if NUMBER_RE.search(expected) and roll < 0.55:
            return _mutate_numbers(expected, rng)
        if context_sentences and roll < 0.8:
            return rng.choice(HEDGES) + rng.choice(context_sentences)
        return rng.choice(HEDGES) + "the answer depends on several factors, so it varies."

    @staticmethod
    def _truncate(text: str, max_tokens: int) -> str:
        limit = max_tokens * 4
        return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0]

    # ------------------------------------------------------------------ judge
    @staticmethod
    def _judge(request: CompletionRequest) -> str:
        """Heuristic stand-in for an LLM judge; returns the same JSON contract a real judge does."""
        from evalplatform.metrics.judge import mock_judge_verdict

        verdict = mock_judge_verdict(request.hints)
        return json.dumps(verdict)
