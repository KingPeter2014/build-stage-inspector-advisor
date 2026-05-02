"""
core/interfaces/observability.py
Abstract tracing and metrics contracts.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator


class AbstractSpan(ABC):
    @abstractmethod
    def set_attribute(self, key: str, value: Any) -> None: ...

    @abstractmethod
    def record_exception(self, exc: Exception) -> None: ...

    @abstractmethod
    def __enter__(self) -> "AbstractSpan": ...

    @abstractmethod
    def __exit__(self, *args: Any) -> None: ...


class AbstractTracer(ABC):
    """
    Uniform tracing interface.
    Implementations: OpenTelemetry (OSS), Azure Monitor, AWS X-Ray, Cloud Trace.
    """

    @abstractmethod
    @contextmanager
    def start_span(self, name: str, attributes: dict[str, Any] | None = None) -> Generator[AbstractSpan, None, None]:
        """Open a tracing span as a context manager."""


class AbstractMetricsEmitter(ABC):
    """
    Uniform metrics emission interface.
    Implementations: Prometheus (OSS), Azure Monitor Metrics, CloudWatch, Cloud Monitoring.
    """

    @abstractmethod
    def increment_counter(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter metric."""

    @abstractmethod
    def observe_histogram(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a histogram/distribution observation."""

    @abstractmethod
    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge to a specific value."""
