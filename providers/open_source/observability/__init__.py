"""
providers/open_source/observability
Wires OpenTelemetry tracer and Prometheus metrics to core interfaces.
"""
from observability.tracing.tracer import get_tracer  # noqa: F401
from observability.metrics.prometheus_metrics import (  # noqa: F401
    request_counter, token_counter, latency_histogram,
)

from core.interfaces.observability import AbstractTracer, AbstractSpan, AbstractMetricsEmitter
from contextlib import contextmanager
from opentelemetry import trace
from typing import Any


class _OTelSpan(AbstractSpan):
    def __init__(self, span):
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def record_exception(self, exc: Exception) -> None:
        self._span.record_exception(exc)

    def __enter__(self) -> "_OTelSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class OSSTracer(AbstractTracer):
    """AbstractTracer backed by OpenTelemetry with OTLP export to Jaeger/Langfuse."""

    def __init__(self, service_name: str = "llmops-oss"):
        self._tracer = get_tracer(service_name)

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield _OTelSpan(span)


class OSSMetricsEmitter(AbstractMetricsEmitter):
    """AbstractMetricsEmitter backed by Prometheus client."""

    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        labels = labels or {}
        if name == "requests":
            request_counter.labels(**labels).inc(value)

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        labels = labels or {}
        if name == "latency":
            latency_histogram.labels(**labels).observe(value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        pass  # Extend with output_drift_gauge etc. as needed
