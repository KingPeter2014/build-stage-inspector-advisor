"""
core/interfaces/feature_store.py
Abstract feature store contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FeatureVector:
    entity_id: str
    features: dict[str, Any]
    event_timestamp: datetime = field(default_factory=datetime.utcnow)


class AbstractFeatureStore(ABC):
    """
    Uniform interface for feature stores.
    Implementations: Feast (OSS), Azure ML Feature Store, SageMaker Feature Store, Vertex AI Feature Store.
    """

    @abstractmethod
    def get_online_features(
        self,
        feature_refs: list[str],
        entity_rows: list[dict[str, Any]],
    ) -> list[FeatureVector]:
        """Retrieve low-latency online features for a batch of entities."""

    @abstractmethod
    def get_historical_features(
        self,
        feature_refs: list[str],
        entity_df: Any,  # pandas DataFrame with entity keys + event_timestamp
    ) -> Any:
        """Retrieve point-in-time correct historical features for training."""

    @abstractmethod
    def materialize(self, start: datetime, end: datetime) -> None:
        """Push features from the offline store to the online store."""
