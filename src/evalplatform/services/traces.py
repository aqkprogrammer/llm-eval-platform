"""Helpers for persisting collected spans."""

from __future__ import annotations

from evalplatform.db.models import Span
from evalplatform.tracing import SpanRecord


def span_rows(records: list[SpanRecord], trace_id: str) -> list[Span]:
    return [
        Span(
            id=r.id,
            trace_id=trace_id,
            parent_id=r.parent_id,
            name=r.name,
            kind=r.kind,
            status=r.status,
            start_time=r.start_time,
            end_time=r.end_time,
            duration_ms=r.duration_ms,
            attributes=_jsonable(r.attributes),
            error=r.error,
        )
        for r in records
    ]


def _jsonable(attrs: dict[str, object]) -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in attrs.items():
        out[k] = v if isinstance(v, str | int | float | bool | type(None) | list | dict) else str(v)
    return out
