"""Aggregation of per-case metric scores and threshold gate evaluation."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from evalplatform.metrics.registry import get_metric_class

QUALITY_CATEGORIES = {"accuracy", "hallucination", "relevancy", "safety"}


@dataclass(slots=True)
class ScorePoint:
    metric: str
    value: float | None
    passed: bool | None


def percentile(values: list[float], q: float) -> float:
    if not values:
        return math.nan
    ordered = sorted(values)
    k = (len(ordered) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def metric_meta(name: str) -> dict[str, Any]:
    try:
        cls = get_metric_class(name)
        return {
            "higher_is_better": cls.higher_is_better,
            "unit": cls.unit,
            "category": cls.category,
        }
    except KeyError:
        return {"higher_is_better": True, "unit": "score", "category": "custom"}


def aggregate(points: Iterable[ScorePoint]) -> dict[str, dict[str, Any]]:
    by_metric: dict[str, list[ScorePoint]] = defaultdict(list)
    for p in points:
        by_metric[p.metric].append(p)
    out: dict[str, dict[str, Any]] = {}
    for metric, pts in sorted(by_metric.items()):
        values = [p.value for p in pts if p.value is not None]
        judged = [p.passed for p in pts if p.passed is not None]
        meta = metric_meta(metric)
        out[metric] = {
            **meta,
            "n": len(values),
            "skipped": len(pts) - len(values),
            "mean": _r(sum(values) / len(values)) if values else None,
            "p50": _r(percentile(values, 0.5)) if values else None,
            "p95": _r(percentile(values, 0.95)) if values else None,
            "min": _r(min(values)) if values else None,
            "max": _r(max(values)) if values else None,
            "sum": _r(sum(values)) if values else None,
            "pass_rate": _r(sum(judged) / len(judged)) if judged else None,
        }
    return out


def _r(x: float) -> float:
    return round(x, 6)


def composite_score(aggregates: dict[str, dict[str, Any]]) -> float | None:
    """Mean of normalised quality metrics (0-1 scores; lower-is-better ones are inverted)."""
    parts: list[float] = []
    for agg in aggregates.values():
        if agg["category"] not in QUALITY_CATEGORIES or agg["mean"] is None:
            continue
        if agg["unit"] != "score":
            continue
        mean = float(agg["mean"])
        parts.append(mean if agg["higher_is_better"] else 1 - min(1.0, mean))
    return round(sum(parts) / len(parts), 4) if parts else None


def normalize_thresholds(raw: dict[str, Any]) -> dict[str, dict[str, float]]:
    """``{"faithfulness": 0.8, "latency_ms": {"max": 1500}}`` -> explicit min/max bounds.

    A bare number means "at least" for higher-is-better metrics and "at most" otherwise.
    ``pass_rate`` gates the share of cases whose metrics all passed.
    """
    out: dict[str, dict[str, float]] = {}
    for metric, spec in (raw or {}).items():
        if isinstance(spec, dict):
            bounds = {k: float(v) for k, v in spec.items() if k in {"min", "max"}}
            if not bounds:
                raise ValueError(f"Threshold for '{metric}' needs 'min' and/or 'max'")
        else:
            higher = True if metric == "pass_rate" else metric_meta(metric)["higher_is_better"]
            bounds = {"min": float(spec)} if higher else {"max": float(spec)}
        out[metric] = bounds
    return out


def evaluate_gates(
    variant_summary: dict[str, Any], thresholds: dict[str, dict[str, float]]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for metric, bounds in thresholds.items():
        if metric == "pass_rate":
            actual = variant_summary.get("pass_rate")
        else:
            actual = (variant_summary.get("metrics", {}).get(metric) or {}).get("mean")
        ok = actual is not None
        if ok and "min" in bounds:
            ok = actual >= bounds["min"]
        if ok and "max" in bounds:
            ok = actual <= bounds["max"]
        results.append({"metric": metric, "actual": actual, **bounds, "passed": bool(ok)})
    return results
