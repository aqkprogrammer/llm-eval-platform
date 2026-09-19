"""OpenTelemetry setup with pluggable exporters (console, OTLP, Langfuse).

Langfuse (v3+) ingests OpenTelemetry natively at ``{host}/api/public/otel``, so instead of pulling
in the Langfuse SDK we attach a second OTLP/HTTP exporter authenticated with the project keys.
"""

from __future__ import annotations

import base64
from typing import Any

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SimpleSpanProcessor,
    SpanExporter,
)

from evalplatform.config import Settings
from evalplatform.logging import get_logger

log = get_logger(__name__)


def build_tracer_provider(settings: Settings) -> TracerProvider | None:
    if not settings.otel_enabled:
        return None
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    exporters: list[str] = []
    if settings.otel_exporter == "console":
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        exporters.append("console")
    elif settings.otel_exporter == "otlp":
        provider.add_span_processor(BatchSpanProcessor(_otlp(settings.otel_exporter_otlp_endpoint)))
        exporters.append("otlp")
    if settings.langfuse_enabled:
        provider.add_span_processor(BatchSpanProcessor(_langfuse_exporter(settings)))
        exporters.append("langfuse")
    log.info("otel.configured", exporters=exporters or ["none"])
    return provider


def _otlp(endpoint: str | None, headers: dict[str, str] | None = None) -> SpanExporter:
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    kwargs: dict[str, Any] = {}
    if endpoint:
        kwargs["endpoint"] = endpoint.rstrip("/") + (
            "" if endpoint.rstrip("/").endswith("/v1/traces") else "/v1/traces"
        )
    if headers:
        kwargs["headers"] = headers
    return OTLPSpanExporter(**kwargs)


def _langfuse_exporter(settings: Settings) -> SpanExporter:
    token = base64.b64encode(
        f"{settings.langfuse_public_key}:{settings.langfuse_secret_key}".encode()
    ).decode()
    endpoint = settings.langfuse_host.rstrip("/") + "/api/public/otel"
    return _otlp(endpoint, {"Authorization": f"Basic {token}"})
