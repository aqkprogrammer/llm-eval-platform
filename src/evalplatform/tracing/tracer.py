"""Lightweight tracer that records spans to the platform DB *and* mirrors them to OpenTelemetry.

Usage::

    tracer = get_tracer()
    with tracer.trace("experiment.case") as collector:
        async with tracer.span("llm.generate", kind="llm", model="x") as span:
            span.set("output_tokens", 42)
    collector.spans  # -> list[SpanRecord], ready to persist

Context propagation uses ``contextvars`` so spans created in concurrently running asyncio tasks
(e.g. metrics evaluated in parallel) nest under the right parent automatically.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from opentelemetry.trace import Status, StatusCode

from evalplatform.db.base import new_id

_collector: ContextVar[TraceCollector | None] = ContextVar("eval_trace_collector", default=None)
_current_span: ContextVar[SpanRecord | None] = ContextVar("eval_current_span", default=None)


@dataclass(slots=True)
class SpanRecord:
    name: str
    kind: str
    trace_id: str
    parent_id: str | None
    start_time: datetime
    id: str = field(default_factory=new_id)
    end_time: datetime | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None


@dataclass(slots=True)
class TraceCollector:
    trace_id: str
    name: str
    spans: list[SpanRecord] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: datetime | None = None


class SpanHandle:
    def __init__(self, record: SpanRecord, otel_span: Any | None) -> None:
        self.record = record
        self._otel = otel_span

    @property
    def id(self) -> str:
        return self.record.id

    def set(self, key: str, value: Any) -> None:
        self.record.attributes[key] = value
        if self._otel is not None and value is not None:
            self._otel.set_attribute(key, _otel_value(value))

    def update(self, **attrs: Any) -> None:
        for k, v in attrs.items():
            self.set(k, v)


def _otel_value(value: Any) -> Any:
    if isinstance(value, bool | int | float | str):
        return value
    text = str(value)
    return text if len(text) <= 4000 else text[:4000] + "…"


class Tracer:
    def __init__(self, otel_provider: Any | None = None) -> None:
        self._otel = otel_provider.get_tracer("evalplatform") if otel_provider else None
        self._provider = otel_provider

    @contextmanager
    def trace(self, name: str, trace_id: str | None = None) -> Iterator[TraceCollector]:
        collector = TraceCollector(trace_id=trace_id or new_id(), name=name)
        token = _collector.set(collector)
        span_token = _current_span.set(None)
        try:
            yield collector
        finally:
            collector.end_time = datetime.now(UTC)
            _current_span.reset(span_token)
            _collector.reset(token)

    @asynccontextmanager
    async def span(
        self, name: str, kind: str = "internal", **attributes: Any
    ) -> AsyncIterator[SpanHandle]:
        collector = _collector.get()
        parent = _current_span.get()
        record = SpanRecord(
            name=name,
            kind=kind,
            trace_id=collector.trace_id if collector else new_id(),
            parent_id=parent.id if parent else None,
            start_time=datetime.now(UTC),
            attributes={k: v for k, v in attributes.items() if v is not None},
        )
        started = time.perf_counter()
        token = _current_span.set(record)
        otel_cm = (
            self._otel.start_as_current_span(name, attributes={"eval.kind": kind})
            if self._otel
            else None
        )
        otel_span = otel_cm.__enter__() if otel_cm else None
        handle = SpanHandle(record, otel_span)
        for k, v in record.attributes.items():
            handle.set(k, v)
        error: BaseException | None = None
        try:
            yield handle
        except BaseException as exc:
            error = exc
            record.status = "error"
            record.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            record.duration_ms = round(elapsed, 3)
            record.end_time = record.start_time + timedelta(milliseconds=record.duration_ms)
            _current_span.reset(token)
            if collector is not None:
                collector.spans.append(record)
            if otel_cm is not None:
                if error is None:
                    if otel_span is not None:
                        otel_span.set_status(Status(StatusCode.OK))
                    otel_cm.__exit__(None, None, None)
                else:
                    otel_cm.__exit__(type(error), error, error.__traceback__)

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()


_tracer: Tracer | None = None


def get_tracer() -> Tracer:
    global _tracer
    if _tracer is None:
        _tracer = Tracer(None)
    return _tracer


def set_tracer(tracer: Tracer) -> None:
    global _tracer
    _tracer = tracer
