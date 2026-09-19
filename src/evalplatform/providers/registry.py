"""Provider registry: resolves a provider name to a (cached) provider instance."""

from __future__ import annotations

from evalplatform.config import Settings, get_settings
from evalplatform.providers.base import LLMProvider, ProviderError

PROVIDER_NAMES = ("mock", "anthropic", "openai", "ollama")


class ProviderRegistry:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._instances: dict[str, LLMProvider] = {}

    def get(self, name: str) -> LLMProvider:
        name = name.lower()
        if name not in self._instances:
            self._instances[name] = self._build(name)
        return self._instances[name]

    def _build(self, name: str) -> LLMProvider:
        s = self.settings
        if name == "mock":
            from evalplatform.providers.mock import MockProvider

            return MockProvider(latency_scale=s.mock_latency_scale)
        if name == "anthropic":
            from evalplatform.providers.anthropic_provider import AnthropicProvider

            return AnthropicProvider(s.anthropic_api_key, s.provider_timeout_s)
        if name == "openai":
            from evalplatform.providers.openai_provider import OpenAIProvider

            return OpenAIProvider(s.openai_api_key, s.openai_base_url, s.provider_timeout_s)
        if name == "ollama":
            from evalplatform.providers.ollama_provider import OllamaProvider

            return OllamaProvider(s.ollama_base_url, s.provider_timeout_s)
        raise ProviderError(f"Unknown provider '{name}'. Known: {', '.join(PROVIDER_NAMES)}")

    def status(self) -> dict[str, bool]:
        s = self.settings
        return {
            "mock": True,
            "anthropic": bool(s.anthropic_api_key),
            "openai": bool(s.openai_api_key),
            "ollama": True,  # reachability is only known at call time
        }

    async def aclose(self) -> None:
        for provider in self._instances.values():
            await provider.aclose()
        self._instances.clear()
