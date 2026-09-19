"""OpenAI (and OpenAI-compatible) chat completions provider."""

from __future__ import annotations

from typing import Any

from evalplatform.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
    Stopwatch,
    estimate_tokens,
)


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(
        self, api_key: str | None, base_url: str | None = None, timeout_s: float = 60.0
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout_s
        self._client: Any = None

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def _get_client(self) -> Any:
        if not self._api_key:
            raise ProviderError("OPENAI_API_KEY is not set")
        if self._client is None:
            import openai

            self._client = openai.AsyncOpenAI(
                api_key=self._api_key, base_url=self._base_url, timeout=self._timeout
            )
        return self._client

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        client = self._get_client()
        messages: list[dict[str, str]] = []
        if request.system:
            messages.append({"role": "system", "content": request.system})
        messages.append({"role": "user", "content": request.user})
        kwargs: dict[str, Any] = {
            "model": request.model,
            "messages": messages,
            "max_completion_tokens": request.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        kwargs.update(request.params)
        watch = Stopwatch()
        chunks: list[str] = []
        usage: Any = None
        finish: str | None = None
        model = request.model
        try:
            stream = await client.chat.completions.create(**kwargs)
            async for chunk in stream:
                model = chunk.model or model
                if chunk.usage is not None:
                    usage = chunk.usage
                for choice in chunk.choices:
                    if choice.delta and choice.delta.content:
                        watch.mark_first_token()
                        chunks.append(choice.delta.content)
                    if choice.finish_reason:
                        finish = choice.finish_reason
        except Exception as exc:
            raise ProviderError(f"OpenAI request failed: {exc}") from exc
        text = "".join(chunks)
        return CompletionResponse(
            text=text,
            model=model,
            provider=self.name,
            input_tokens=usage.prompt_tokens
            if usage
            else estimate_tokens((request.system or "") + request.user),
            output_tokens=usage.completion_tokens if usage else estimate_tokens(text),
            latency_ms=watch.elapsed_ms,
            ttft_ms=watch.ttft_ms,
            finish_reason=finish,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
