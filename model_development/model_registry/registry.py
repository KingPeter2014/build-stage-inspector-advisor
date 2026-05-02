"""
model_development/model_registry/registry.py
Model registry abstraction — wraps MLflow Model Registry.
Manages champion/challenger lifecycle, model cards, and lineage.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any

import mlflow
from mlflow.tracking import MlflowClient


class ModelStage(str, Enum):
    STAGING = "Staging"
    PRODUCTION = "Production"
    ARCHIVED = "Archived"
    CHALLENGER = "Challenger"


@dataclass
class ModelCard:
    """Documentation artefact required for compliance and reproducibility."""
    model_name: str
    version: int
    base_model: str
    training_data_sources: list[str]
    fine_tuning_config: dict[str, Any]
    eval_metrics: dict[str, float]
    intended_use: str
    known_limitations: str
    pii_in_training_data: bool
    training_data_cutoff: str
    created_by: str
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


class ModelRegistry:
    def __init__(self, tracking_uri: str = "http://localhost:5000"):
        mlflow.set_tracking_uri(tracking_uri)
        self.client = MlflowClient()

    def register(
        self,
        run_id: str,
        model_name: str,
        artifact_path: str = "model",
        model_card: ModelCard | None = None,
    ) -> mlflow.entities.model_registry.ModelVersion:
        """Register a model from an MLflow run."""
        model_uri = f"runs:/{run_id}/{artifact_path}"
        mv = mlflow.register_model(model_uri=model_uri, name=model_name)

        if model_card:
            self.client.update_model_version(
                name=model_name,
                version=mv.version,
                description=str(model_card.to_dict()),
            )
            for k, v in model_card.eval_metrics.items():
                self.client.set_model_version_tag(model_name, mv.version, k, str(v))

        return mv

    def promote(self, model_name: str, version: int, stage: ModelStage) -> None:
        self.client.transition_model_version_stage(
            name=model_name,
            version=str(version),
            stage=stage.value,
            archive_existing_versions=(stage == ModelStage.PRODUCTION),
        )

    def get_production_version(self, model_name: str) -> int | None:
        versions = self.client.get_latest_versions(model_name, stages=["Production"])
        return int(versions[0].version) if versions else None

    def get_challenger_version(self, model_name: str) -> int | None:
        versions = self.client.get_latest_versions(model_name, stages=["Staging"])
        return int(versions[0].version) if versions else None

    def champion_challenger_swap(self, model_name: str) -> None:
        """Promote Staging → Production, archive old Production."""
        challenger = self.get_challenger_version(model_name)
        if challenger is None:
            raise ValueError("No challenger model in Staging")
        self.promote(model_name, challenger, ModelStage.PRODUCTION)

    def list_versions(self, model_name: str) -> list[dict]:
        versions = self.client.search_model_versions(f"name='{model_name}'")
        return [
            {
                "version": v.version,
                "stage": v.current_stage,
                "run_id": v.run_id,
                "created_at": v.creation_timestamp,
            }
            for v in versions
        ]
