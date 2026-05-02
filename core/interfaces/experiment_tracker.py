"""
core/interfaces/experiment_tracker.py
Abstract experiment tracker contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Generator


class AbstractExperimentTracker(ABC):
    """
    Uniform interface for ML experiment tracking.
    Implementations: MLflow/W&B (OSS), Azure ML Experiments, SageMaker Experiments, Vertex AI Experiments.
    """

    @abstractmethod
    @contextmanager
    def run(self, run_name: str, tags: dict[str, str] | None = None) -> Generator["AbstractExperimentTracker", None, None]:
        """Context manager that opens a run and yields self for chained logging."""

    @abstractmethod
    def log_params(self, params: dict[str, Any]) -> None:
        """Log hyper-parameters for the current run."""

    @abstractmethod
    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log scalar metrics, optionally at a training step."""

    @abstractmethod
    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        """Upload a file or directory as a run artifact."""

    @abstractmethod
    def set_tag(self, key: str, value: str) -> None:
        """Attach a key-value tag to the current run."""
