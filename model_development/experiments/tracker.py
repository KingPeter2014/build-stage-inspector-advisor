"""
model_development/experiments/tracker.py
Unified experiment tracking — wraps MLflow and W&B behind a common interface.
"""
from __future__ import annotations

from contextlib import contextmanager
from enum import Enum
from typing import Any


class Backend(str, Enum):
    MLFLOW = "mlflow"
    WANDB = "wandb"


class ExperimentTracker:
    def __init__(self, backend: Backend = Backend.MLFLOW, **kwargs):
        self.backend = backend
        self._run = None

        if backend == Backend.MLFLOW:
            import mlflow
            mlflow.set_tracking_uri(kwargs.get("tracking_uri", "http://localhost:5000"))
            mlflow.set_experiment(kwargs.get("experiment_name", "llmops-default"))
            self._mlflow = mlflow
        elif backend == Backend.WANDB:
            import wandb
            self._wandb = wandb
            self._wandb_kwargs = kwargs

    @contextmanager
    def run(self, run_name: str, tags: dict[str, str] | None = None):
        if self.backend == Backend.MLFLOW:
            with self._mlflow.start_run(run_name=run_name, tags=tags) as run:
                self._run = run
                yield self
        elif self.backend == Backend.WANDB:
            self._run = self._wandb.init(name=run_name, tags=list((tags or {}).values()), **self._wandb_kwargs)
            yield self
            self._run.finish()

    def log_params(self, params: dict[str, Any]) -> None:
        if self.backend == Backend.MLFLOW:
            self._mlflow.log_params(params)
        elif self.backend == Backend.WANDB:
            self._wandb.config.update(params)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        if self.backend == Backend.MLFLOW:
            self._mlflow.log_metrics(metrics, step=step)
        elif self.backend == Backend.WANDB:
            self._wandb.log({**metrics, **({"step": step} if step else {})})

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        if self.backend == Backend.MLFLOW:
            self._mlflow.log_artifact(local_path, artifact_path)
        elif self.backend == Backend.WANDB:
            self._wandb.save(local_path)

    def set_tag(self, key: str, value: str) -> None:
        if self.backend == Backend.MLFLOW:
            self._mlflow.set_tag(key, value)
