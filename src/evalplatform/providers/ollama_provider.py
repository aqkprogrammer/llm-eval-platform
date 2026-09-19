"""Ollama provider for local open-source models (streams NDJSON from ``/api/chat``)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from evalplatform.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
    Stopwatch,
    estimate_tokens,
)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, base_url: str, timeout_s: float = 120.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})
        options: dict[str, Any] = {"num_predict": request.max_tokens}
        if request.temperature is not None:
            options["temperature"] = request.temperature
        options.update(request.params.get("options", {}))
        payload = {"model": request.model, "messages": messages, "stream": True, "options": options}
        watch = Stopwatch()
        chunks: list[str] = []
        final: dict[str, Any] = {}
        try:
            async with self._client.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode(errors="replace")
                    raise ProviderError(f"Ollama returned {resp.status_code}: {body[:300]}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    content = data.get("message", {}).get("content", "")
                    if content:
                        watch.mark_first_token()
                        chunks.append(content)
                    if data.get("done"):
                        final = data
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        text = "".join(chunks)
        return CompletionResponse(
            text=text,
            model=request.model,
            provider=self.name,
            input_tokens=int(
                final.get("prompt_eval_count")
                or estimate_tokens((request.system or "") + request.user)
            ),
            output_tokens=int(final.get("eval_count") or estimate_tokens(text)),
            latency_ms=watch.elapsed_ms,
            ttft_ms=watch.ttft_ms,
            finish_reason=final.get("done_reason"),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
