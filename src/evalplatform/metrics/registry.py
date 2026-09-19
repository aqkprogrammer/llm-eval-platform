"""Metric registry: name -> Metric class, plus factory helpers."""

from __future__ import annotations

from typing import Any

from evalplatform.metrics.base import Metric

_REGISTRY: dict[str, type[Metric]] = {}


def register[M: type[Metric]](cls: M) -> M:
    if cls.name in _REGISTRY:
        raise ValueError(f"Metric '{cls.name}' registered twice")
    _REGISTRY[cls.name] = cls
    return cls


def _ensure_loaded() -> None:
    # Importing the modules registers their metrics.
    from evalplatform.metrics import (  # noqa: F401
        accuracy,
        faithfulness,
        judge,
        performance,
        relevancy,
        safety,
    )
    from evalplatform.metrics.adapters import deepeval_adapter, ragas_adapter  # noqa: F401


def get_metric_class(name: str) -> type[Metric]:
    _ensure_loaded()
    try:
        return _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown metric '{name}'. Available: {', '.join(sorted(_REGISTRY))}"
        ) from None


def all_metric_classes() -> list[type[Metric]]:
    _ensure_loaded()
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def normalize_spec(spec: str | dict[str, Any]) -> dict[str, Any]:
    """Accept ``"faithfulness"`` or ``{"name": "faithfulness", "threshold": 0.9, "params": {}}``."""
    if isinstance(spec, str):
        return {"name": spec, "threshold": None, "params": {}}
    if "name" not in spec:
        raise ValueError(f"Metric spec is missing 'name': {spec!r}")
    return {
        "name": spec["name"],
        "threshold": spec.get("threshold"),
        "params": dict(spec.get("params") or {}),
    }


def create_metric(spec: str | dict[str, Any]) -> Metric:
    norm = normalize_spec(spec)
    cls = get_metric_class(norm["name"])
    if not cls.is_available():
        raise RuntimeError(
            f"Metric '{cls.name}' requires an optional dependency; install the "
            f"'{cls.backend}' extra (uv sync --extra {cls.backend})."
        )
    return cls(threshold=norm["threshold"], **norm["params"])


DEFAULT_METRICS = [
    "correctness",
    "semantic_similarity",
    "fuzzy_match",
    "faithfulness",
    "answer_relevancy",
    "toxicity",
    "pii_leakage",
    "prompt_injection",
    "jailbreak_resistance",
    "latency_ms",
    "ttft_ms",
    "total_tokens",
    "cost_usd",
]
