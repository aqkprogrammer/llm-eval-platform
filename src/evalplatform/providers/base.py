"""Provider abstraction shared by all LLM backends."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class ProviderError(RuntimeError):
    """Raised when a provider call fails or a provider is misconfigured."""


@dataclass(slots=True)
class CompletionRequest:
    model: str
    user: str
    system: str | None = None
    temperature: float | None = 0.0
    max_tokens: int = 512
    params: dict[str, Any] = field(default_factory=dict)
    hints: dict[str, Any] = field(default_factory=dict)
    """Side-channel metadata (test case, context, task). Only the ``mock`` provider reads it,
    to simulate realistic behaviour offline; real providers ignore it entirely."""


@dataclass(slots=True)
class CompletionResponse:
    text: str
    model: str
    provider: str
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    ttft_ms: float | None = None
    finish_reason: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class Stopwatch:
    """Measures total latency and time-to-first-token for streaming calls."""

    def __init__(self) -> None:
        self._start = time.perf_counter()
        self._first: float | None = None

    def mark_first_token(self) -> None:
        if self._first is None:
            self._first = time.perf_counter()

    @property
    def ttft_ms(self) -> float | None:
        return None if self._first is None else (self._first - self._start) * 1000

    @property
    def elapsed_ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000


class LLMProvider(ABC):
    """An LLM backend. Implementations should stream so TTFT can be measured."""

    name: str = "base"

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...

    def is_configured(self) -> bool:
        return True

    async def aclose(self) -> None:  # pragma: no cover - default no-op
        return None


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token) used when a backend does not report usage."""
    if not text:
        return 0
    return max(1, round(len(text) / 4))
