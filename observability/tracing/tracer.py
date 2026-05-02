"""
observability/tracing/tracer.py
Configures OpenTelemetry tracing with OTLP export (Jaeger / Langfuse-compatible).
"""
from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

_provider_initialized = False


def _init_provider(service_name: str = "llmops-service", otlp_endpoint: str = "") -> None:
    global _provider_initialized
    if _provider_initialized:
        return

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    else:
        exporter = ConsoleSpanExporter()

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _provider_initialized = True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer for the given component name."""
    try:
        from config.settings import get_settings
        s = get_settings()
        _init_provider(service_name=s.otel_service_name, otlp_endpoint=s.otel_exporter_otlp_endpoint)
    except Exception:
        _init_provider()
    return trace.get_tracer(name)
