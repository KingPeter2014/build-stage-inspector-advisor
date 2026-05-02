"""
storage/feature_store/feast_store.py
Feature store wrapper using Feast for structured features used in
reranking, routing decisions, and fine-tuning dataset construction.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pandas as pd


@dataclass
class FeatureVector:
    entity_id: str
    features: dict[str, Any]
    retrieved_at: str


class FeastFeatureStore:
    """
    Wraps Feast for online feature retrieval.
    Offline store (for training) uses the same registry.
    """

    def __init__(self, repo_path: str = "storage/feature_store"):
        try:
            from feast import FeatureStore
            self._store = FeatureStore(repo_path=repo_path)
        except ImportError:
            self._store = None

    def get_online_features(
        self,
        feature_refs: list[str],
        entity_rows: list[dict[str, Any]],
    ) -> list[FeatureVector]:
        """
        Retrieve online features for a list of entities.

        Example:
            store.get_online_features(
                feature_refs=["user_features:query_count_7d", "user_features:avg_session_len"],
                entity_rows=[{"user_id": "u123"}],
            )
        """
        if self._store is None:
            return []
        response = self._store.get_online_features(
            features=feature_refs,
            entity_rows=entity_rows,
        ).to_dict()

        results = []
        for i, row in enumerate(entity_rows):
            features = {k: v[i] for k, v in response.items() if k not in row}
            entity_id = next(iter(row.values()), str(i))
            results.append(FeatureVector(
                entity_id=str(entity_id),
                features=features,
                retrieved_at=datetime.utcnow().isoformat(),
            ))
        return results

    def get_historical_features(
        self,
        feature_refs: list[str],
        entity_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Retrieve historical features for training dataset construction.
        entity_df must include an 'event_timestamp' column.
        """
        if self._store is None:
            return entity_df
        job = self._store.get_historical_features(
            features=feature_refs,
            entity_df=entity_df,
        )
        return job.to_df()

    def materialize(self, start_date: datetime, end_date: datetime) -> None:
        """Materialise features from offline to online store."""
        if self._store:
            self._store.materialize(start_date=start_date, end_date=end_date)


# ── Example Feast feature definitions (normally in feature_store/features.py) ──

EXAMPLE_FEATURE_DEFINITIONS = '''
# storage/feature_store/features.py
# Run: feast apply  to register these

from feast import Entity, FeatureView, Field, FileSource
from feast.types import Float64, Int64, String
from datetime import timedelta

user = Entity(name="user_id", description="LLMOps user identifier")

user_stats_source = FileSource(
    path="data/feature_store/user_stats.parquet",
    timestamp_field="event_timestamp",
)

user_feature_view = FeatureView(
    name="user_features",
    entities=[user],
    ttl=timedelta(days=7),
    schema=[
        Field(name="query_count_7d", dtype=Int64),
        Field(name="avg_session_len", dtype=Float64),
        Field(name="preferred_model", dtype=String),
        Field(name="avg_feedback_score", dtype=Float64),
    ],
    source=user_stats_source,
)
'''
