"""Per-model token pricing (USD per 1M tokens) and cost calculation.

Prices change frequently; the built-in table is a sensible default and can be overridden with a
YAML/JSON file via ``PRICING_FILE``::

    claude-sonnet-5: {input: 3.0, output: 15.0}
    my-finetune: {input: 0.5, output: 1.5}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input: float
    output: float


DEFAULT_PRICING: dict[str, ModelPrice] = {
    # Anthropic
    "claude-sonnet-5": ModelPrice(3.0, 15.0),
    "claude-opus-5": ModelPrice(5.0, 25.0),
    "claude-haiku-4-5": ModelPrice(1.0, 5.0),
    # OpenAI
    "gpt-4o": ModelPrice(2.5, 10.0),
    "gpt-4o-mini": ModelPrice(0.15, 0.6),
    "gpt-4.1": ModelPrice(2.0, 8.0),
    "gpt-4.1-mini": ModelPrice(0.4, 1.6),
    # Mock models (fictional prices so cost metrics are meaningful offline)
    "mock-gpt-large": ModelPrice(5.0, 15.0),
    "mock-fast-small": ModelPrice(0.2, 0.8),
    "mock-llama-base": ModelPrice(0.0, 0.0),
    "mock-judge": ModelPrice(0.0, 0.0),
}
FREE_PROVIDERS = {"ollama"}


class PricingTable:
    def __init__(self, prices: dict[str, ModelPrice]) -> None:
        self._prices = dict(prices)

    def get(self, model: str, provider: str | None = None) -> ModelPrice | None:
        if provider in FREE_PROVIDERS:
            return ModelPrice(0.0, 0.0)
        if model in self._prices:
            return self._prices[model]
        # Match dated snapshots such as "gpt-4o-2024-08-06" to their family entry.
        for name in sorted(self._prices, key=len, reverse=True):
            if model.startswith(name):
                return self._prices[name]
        return None

    def cost(
        self, model: str, input_tokens: int, output_tokens: int, provider: str | None = None
    ) -> float:
        price = self.get(model, provider)
        if price is None:
            return 0.0
        return round((input_tokens * price.input + output_tokens * price.output) / 1_000_000, 8)

    def as_dict(self) -> dict[str, dict[str, float]]:
        return {k: {"input": v.input, "output": v.output} for k, v in sorted(self._prices.items())}


def load_pricing(path: Path | None) -> PricingTable:
    prices = dict(DEFAULT_PRICING)
    if path is not None and Path(path).exists():
        text = Path(path).read_text()
        data = json.loads(text) if str(path).endswith(".json") else yaml.safe_load(text)
        for model, entry in (data or {}).items():
            prices[str(model)] = ModelPrice(float(entry["input"]), float(entry["output"]))
    return PricingTable(prices)


@lru_cache
def get_pricing() -> PricingTable:
    from evalplatform.config import get_settings

    return load_pricing(get_settings().pricing_file)
