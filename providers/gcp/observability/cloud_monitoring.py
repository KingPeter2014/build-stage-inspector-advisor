"""
providers/gcp/observability/cloud_monitoring.py
Google Cloud Monitoring metrics + Cloud Trace — AbstractTracer / AbstractMetricsEmitter.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

from google.cloud import monitoring_v3
from opentelemetry import trace
from opentelemetry.exporter.cloud_trace import CloudTraceSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from core.interfaces.observability import AbstractMetricsEmitter, AbstractSpan, AbstractTracer
from providers.gcp.config.settings import get_gcp_settings

_initialized = False


def _init_cloud_trace() -> None:
    global _initialized
    if _initialized:
        return
    s = get_gcp_settings()
    resource = Resource.create({"service.name": "llmops-gcp", "gcp.project_id": s.gcp_project_id})
    exporter = CloudTraceSpanExporter(project_id=s.gcp_project_id)
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _initialized = True


class _CloudSpan(AbstractSpan):
    def __init__(self, span):
        self._span = span

    def set_attribute(self, key: str, value: Any) -> None:
        self._span.set_attribute(key, value)

    def record_exception(self, exc: Exception) -> None:
        self._span.record_exception(exc)

    def __enter__(self) -> "_CloudSpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class CloudTracer(AbstractTracer):
    """AbstractTracer backed by Google Cloud Trace via OpenTelemetry."""

    def __init__(self, service_name: str = "llmops-gcp") -> None:
        _init_cloud_trace()
        self._tracer = trace.get_tracer(service_name)

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        with self._tracer.start_as_current_span(name) as span:
            if attributes:
                for k, v in attributes.items():
                    span.set_attribute(k, v)
            yield _CloudSpan(span)


class CloudMonitoringMetrics(AbstractMetricsEmitter):
    """AbstractMetricsEmitter backed by Google Cloud Monitoring custom metrics."""

    _METRIC_PREFIX = "custom.googleapis.com/llmops"

    def __init__(self) -> None:
        s = get_gcp_settings()
        self._project_name = f"projects/{s.gcp_project_id}"
        self._client = monitoring_v3.MetricServiceClient()
        self._project_id = s.gcp_project_id

    def _write_time_series(self, metric_type: str, value: float,
                            labels: dict[str, str] | None = None,
                            value_type: str = "double") -> None:
        series = monitoring_v3.TimeSeries()
        series.metric.type = f"{self._METRIC_PREFIX}/{metric_type}"
        for k, v in (labels or {}).items():
            series.metric.labels[k] = v
        series.resource.type = "global"
        series.resource.labels["project_id"] = self._project_id

        now = time.time()
        interval = monitoring_v3.TimeInterval(
            end_time={"seconds": int(now), "nanos": int((now % 1) * 1e9)}
        )
        point = monitoring_v3.Point(interval=interval,
                                    value=monitoring_v3.TypedValue(double_value=value))
        series.points = [point]

        try:
            self._client.create_time_series(
                name=self._project_name, time_series=[series]
            )
        except Exception:
            pass  # Non-fatal — monitoring failures should never break inference

    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._write_time_series(name, value, labels)

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._write_time_series(name, value, labels)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._write_time_series(name, value, labels)
