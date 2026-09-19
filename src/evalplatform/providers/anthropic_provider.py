"""Anthropic Messages API provider (streaming, for accurate TTFT)."""

from __future__ import annotations

from typing import Any

from evalplatform.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
    Stopwatch,
)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, api_key: str | None, timeout_s: float = 60.0) -> None:
        self._api_key = api_key
        self._timeout = timeout_s
        self._client: Any = None

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _get_client(self) -> Any:
        if not self._api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set")
        if self._client is None:
            import anthropic

            self._client = anthropic.AsyncAnthropic(api_key=self._api_key, timeout=self._timeout)
        return self._client

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        client = self._get_client()
        kwargs: dict[str, Any] = {
            "model": request.model,
            "max_tokens": request.max_tokens,
            "messages": [{"role": "user", "content": request.user}],
        }
        if request.system:
            kwargs["system"] = request.system
        # Current Claude models manage sampling themselves; pass-through params (e.g. thinking,
        # output_config) are forwarded verbatim from the model config.
        kwargs.update(request.params)
        watch = Stopwatch()
        chunks: list[str] = []
        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    if text:
                        watch.mark_first_token()
                        chunks.append(text)
                final = await stream.get_final_message()
        except Exception as exc:  # SDK raises a family of APIError subclasses
            raise ProviderError(f"Anthropic request failed: {exc}") from exc
        return CompletionResponse(
            text="".join(chunks),
            model=getattr(final, "model", request.model),
            provider=self.name,
            input_tokens=final.usage.input_tokens,
            output_tokens=final.usage.output_tokens,
            latency_ms=watch.elapsed_ms,
            ttft_ms=watch.ttft_ms,
            finish_reason=getattr(final, "stop_reason", None),
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
