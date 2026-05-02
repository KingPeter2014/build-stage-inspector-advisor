"""
providers/aws/observability/cloudwatch.py
Amazon CloudWatch metrics + AWS X-Ray tracing — AbstractTracer / AbstractMetricsEmitter.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

import boto3

from core.interfaces.observability import AbstractMetricsEmitter, AbstractSpan, AbstractTracer
from providers.aws.config.settings import get_aws_settings


class _XRaySpan(AbstractSpan):
    """Thin wrapper around an X-Ray subsegment."""

    def __init__(self, subsegment):
        self._subseg = subsegment

    def set_attribute(self, key: str, value: Any) -> None:
        if self._subseg:
            self._subseg.put_annotation(key, str(value))

    def record_exception(self, exc: Exception) -> None:
        if self._subseg:
            self._subseg.add_exception(exc, fatal=False)

    def __enter__(self) -> "_XRaySpan":
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class XRayTracer(AbstractTracer):
    """AbstractTracer backed by AWS X-Ray."""

    def __init__(self) -> None:
        try:
            from aws_xray_sdk.core import xray_recorder, patch_all
            patch_all()
            self._recorder = xray_recorder
        except ImportError:
            self._recorder = None

    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None):
        if self._recorder:
            with self._recorder.in_subsegment(name) as subsegment:
                span = _XRaySpan(subsegment)
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                yield span
        else:
            yield _XRaySpan(None)


class CloudWatchMetrics(AbstractMetricsEmitter):
    """AbstractMetricsEmitter backed by Amazon CloudWatch custom metrics."""

    def __init__(self) -> None:
        s = get_aws_settings()
        self._cw = boto3.client("cloudwatch", region_name=s.aws_region)
        self._namespace = s.cloudwatch_namespace
        self._buffer: list[dict] = []
        self._last_flush = time.monotonic()

    def _flush(self, force: bool = False) -> None:
        if not self._buffer:
            return
        if force or len(self._buffer) >= 20 or (time.monotonic() - self._last_flush) > 60:
            self._cw.put_metric_data(Namespace=self._namespace, MetricData=self._buffer)
            self._buffer = []
            self._last_flush = time.monotonic()

    def _dimensions(self, labels: dict[str, str] | None) -> list[dict]:
        return [{"Name": k, "Value": v} for k, v in (labels or {}).items()]

    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        self._buffer.append({
            "MetricName": name, "Value": value,
            "Unit": "Count", "Dimensions": self._dimensions(labels),
        })
        self._flush()

    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._buffer.append({
            "MetricName": name, "Value": value,
            "Unit": "Milliseconds" if "latency" in name.lower() else "None",
            "Dimensions": self._dimensions(labels),
        })
        self._flush()

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        self._buffer.append({
            "MetricName": name, "Value": value,
            "Unit": "None", "Dimensions": self._dimensions(labels),
        })
        self._flush(force=True)
