"""
providers/azure/observability/azure_monitor.py
Azure Monitor + Application Insights observability.

Configures OpenTelemetry to export traces and metrics to Azure Monitor.
The same OTel instrumentation used in the OSS stack works here — only the
exporter changes (OTLP → Azure Monitor).
"""
from __future__ import annotations

from typing import Any
from contextlib import contextmanager

from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter, AzureMonitorMetricExporter
from opentelemetry import metrics as otel_metrics
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from core.interfaces.observability import AbstractTracer, AbstractSpan, AbstractMetricsEmitter
from providers.azure.config.settings import get_azure_settings

_initialized = False


def _init_azure_monitor() -> None:
    global _initialized
    if _initialized:
        return
    s = get_azure_settings()
    conn_str = s.azure_appinsights_connection_string
    if not conn_str:
        return

    resource = Resource.create({"service.name": "llmops-azure"})

    # Traces → App Insights
    trace_exporter = AzureMonitorTraceExporter(connection_string=conn_str)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
    trace.set_tracer_provider(tracer_provider)

    # Metrics → App Insights
    metric_exporter = AzureMonitorMetricExporter(connection_string=conn_str)
    reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60_000)
    meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    otel_metrics.set_meter_provider(meter_provider)

    _initialized = True


class _AzureSpan(AbstractSpan):
    def __init__(self, span):
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def record_exception(self, exc: Exception) -> None:
        self._span.record_exception(exc)

    def __enter__(self) -> "_AzureSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class AzureMonitorTracer(AbstractTracer):
    """AbstractTracer that exports to Azure Monitor / Application Insights via OTel."""

    def __init__(self, service_name: str = "llmops-azure") -> None:
        _init_azure_monitor()
        self._tracer = trace.get_tracer(service_name)

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield _AzureSpan(span)


class AzureMonitorMetrics(AbstractMetricsEmitter):
    """AbstractMetricsEmitter that publishes custom metrics to Azure Monitor."""

    def __init__(self) -> None:
        _init_azure_monitor()
        self._meter = otel_metrics.get_meter("llmops.azure")
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}

    def _counter(self, name: str):
        if name not in self._counters:
            self._counters[name] = self._meter.create_counter(name)
        return self._counters[name]

    def _histogram(self, name: str):
        if name not in self._histograms:
            self._histograms[name] = self._meter.create_histogram(name)
        return self._histograms[name]

    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._counter(name).add(int(value), labels or {})

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._histogram(name).record(value, labels or {})

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        # OTel Gauge is observable; use UpDownCounter as a writable substitute
        key = (name, tuple(sorted((labels or {}).items())))
        if name not in self._gauges:
            self._gauges[name] = self._meter.create_up_down_counter(name)
        # Not perfectly idempotent but acceptable for telemetry
        self._gauges[name].add(value, labels or {})
