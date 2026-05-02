"""
providers/open_source/model_development
Wires MLflow/W&B tracker and MLflow registry to core interfaces.
"""
from model_development.experiments.tracker import ExperimentTracker, Backend  # noqa: F401
from model_development.model_registry.registry import ModelRegistry  # noqa: F401
from model_development.fine_tuning.lora_trainer import train as lora_train  # noqa: F401

from core.interfaces.experiment_tracker import AbstractExperimentTracker
from core.interfaces.model_registry import AbstractModelRegistry, ModelCard, ModelStage
from contextlib import contextmanager
from typing import Any


class OSSExperimentTracker(AbstractExperimentTracker):
    """AbstractExperimentTracker backed by MLflow or Weights & Biases."""

    def __init__(self, backend: str = "mlflow", **kwargs):
        self._tracker = ExperimentTracker(Backend(backend), **kwargs)

    @contextmanager
    def run(self, run_name: str, tags: dict[str, str] | None = None):
        with self._tracker.run(run_name=run_name, tags=tags):
            yield self

    def log_params(self, params: dict[str, Any]) -> None:
        self._tracker.log_params(params)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        self._tracker.log_metrics(metrics, step=step)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        self._tracker.log_artifact(local_path, artifact_path)

    def set_tag(self, key: str, value: str) -> None:
        self._tracker.set_tag(key, value)


class OSSModelRegistry(AbstractModelRegistry):
    """AbstractModelRegistry backed by MLflow Model Registry."""

    def __init__(self, tracking_uri: str = "http://localhost:5000"):
        self._registry = ModelRegistry(tracking_uri=tracking_uri)

    def register(self, run_id: str, model_name: str, artifact_path: str = "model") -> ModelCard:
        version = self._registry.register_model(run_id, model_name, artifact_path)
        return ModelCard(model_name=model_name, version=str(version), stage=ModelStage.STAGING)

    def promote(self, model_name: str, version: str, stage: ModelStage) -> None:
        self._registry.transition_stage(model_name, version, stage.value.title())

    def get_champion(self, model_name: str) -> ModelCard | None:
        card = self._registry.get_champion(model_name)
        if card is None:
            return None
        return ModelCard(model_name=card.model_name, version=card.version,
                         stage=ModelStage.PRODUCTION, metrics=card.metrics)

    def list_versions(self, model_name: str) -> list[ModelCard]:
        versions = self._registry.list_versions(model_name)
        return [ModelCard(model_name=v.model_name, version=v.version,
                          stage=ModelStage(v.stage.lower())) for v in versions]

    def archive(self, model_name: str, version: str) -> None:
        self._registry.transition_stage(model_name, version, "Archived")
