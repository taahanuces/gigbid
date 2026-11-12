from __future__ import annotations

import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import TypeAlias

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span

from agent.security import redact_pii

AttributeValue: TypeAlias = str | bool | int | float
_provider: TracerProvider | None = None


def configure_telemetry() -> TracerProvider | None:
    """Configure an OTLP/HTTP exporter once when an endpoint is explicitly supplied."""
    global _provider
    if _provider is not None:
        return _provider
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "").strip()
    if not endpoint:
        return None

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    headers: dict[str, str] = {}
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    if api_key:
        headers["authorization"] = f"Bearer {api_key}"
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", "gigbid-api"),
                "service.version": "0.1.0",
                "openinference.project.name": os.getenv("OTEL_PROJECT_NAME", "gigbid"),
            }
        )
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
    )
    trace.set_tracer_provider(provider)
    _provider = provider
    return provider


@contextmanager
def trace_span(
    name: str, attributes: Mapping[str, AttributeValue] | None = None
) -> Iterator[Span]:
    """Create a content-free span; string values are PII-redacted before export."""
    safe_attributes = {
        key: redact_pii(value) if isinstance(value, str) else value
        for key, value in (attributes or {}).items()
    }
    tracer = trace.get_tracer("gigbid", "0.1.0")
    with tracer.start_as_current_span(name, attributes=safe_attributes) as span:
        yield span
