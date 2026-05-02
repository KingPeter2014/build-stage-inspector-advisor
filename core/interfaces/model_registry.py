"""
core/interfaces/model_registry.py
Abstract model registry contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ModelStage(str, Enum):
    STAGING = "staging"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    CHALLENGER = "challenger"


@dataclass
class ModelCard:
    """Compliance and reproducibility documentation for a registered model."""
    model_name: str
    version: str
    stage: ModelStage
    description: str = ""
    metrics: dict[str, float] = field(default_factory=dict)
    training_dataset: str = ""
    framework: str = ""
    owner: str = ""
    tags: dict[str, str] = field(default_factory=dict)


class AbstractModelRegistry(ABC):
    """
    Uniform interface for model registries.
    Implementations: MLflow Registry (OSS), Azure ML Registry, SageMaker Registry, Vertex AI Registry.
    """

    @abstractmethod
    def register(self, run_id: str, model_name: str, artifact_path: str = "model") -> ModelCard:
        """Register a trained model from a run; return its ModelCard."""

    @abstractmethod
    def promote(self, model_name: str, version: str, stage: ModelStage) -> None:
        """Move a model version to a new lifecycle stage."""

    @abstractmethod
    def get_champion(self, model_name: str) -> ModelCard | None:
        """Return the current production (champion) model card, or None."""

    @abstractmethod
    def list_versions(self, model_name: str) -> list[ModelCard]:
        """Return all registered versions of a model."""

    @abstractmethod
    def archive(self, model_name: str, version: str) -> None:
        """Move a version to the archived stage."""
