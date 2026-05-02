"""
providers/gcp/config/settings.py
GCP-specific environment configuration.

Load order (later overrides earlier):
  1. .env
  2. .env.<APP_ENV>  (e.g. .env.staging, .env.production)
  3. actual environment variables (highest priority — used in CI and Cloud Run runtime)

In production, google_application_credentials must be empty:
use the Cloud Run service account binding (Workload Identity) instead.
"""
from __future__ import annotations

import os
import warnings
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.getenv("APP_ENV", "development")


class GCPSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_APP_ENV}"),
        extra="ignore",
    )

    @model_validator(mode="after")
    def _warn_prod_sa_key(self) -> "GCPSettings":
        if _APP_ENV == "production" and self.google_application_credentials:
            warnings.warn(
                "google_application_credentials (service account key file) is set in production. "
                "Use Cloud Run service account binding (Workload Identity) instead.",
                stacklevel=2,
            )
        if not self.gcp_redis_url and os.getenv("REDIS_HOST"):
            port = os.getenv("REDIS_PORT", "6379")
            self.gcp_redis_url = f"redis://{os.getenv('REDIS_HOST')}:{port}"
        return self

    # ── GCP Project & Auth ────────────────────────────────────────────────────
    gcp_project_id: str = ""
    gcp_region: str = "us-central1"
    google_application_credentials: str = ""  # Path to service account JSON

    # ── Vertex AI ─────────────────────────────────────────────────────────────
    vertex_model_id: str = "gemini-1.5-pro-002"
    vertex_embedding_model: str = "text-embedding-005"

    # ── Vertex AI Vector Search ───────────────────────────────────────────────
    vertex_index_id: str = ""           # Deployed index resource ID
    vertex_index_endpoint_id: str = Field(
        default="",
        validation_alias=AliasChoices("VERTEX_INDEX_ENDPOINT_ID", "VECTOR_SEARCH_INDEX_ENDPOINT"),
    )
    vertex_deployed_index_id: str = Field(
        default="llmops_deployed_index",
        validation_alias=AliasChoices(
            "VERTEX_DEPLOYED_INDEX_ID",
            "VECTOR_SEARCH_DEPLOYED_INDEX_ID",
        ),
    )
    vertex_vector_dim: int = 768        # text-embedding-005 output dimension

    # ── Vertex AI Agent Engine ────────────────────────────────────────────────
    vertex_agent_engine_id: str = ""    # ReasoningEngine resource ID

    # ── Google Cloud Storage ──────────────────────────────────────────────────
    gcs_bucket: str = Field(
        default="llmops-data",
        validation_alias=AliasChoices("GCS_BUCKET", "GCS_BUCKET_NAME"),
    )
    gcs_prefix: str = "llmops"

    # ── Vertex AI Experiments ─────────────────────────────────────────────────
    vertex_experiment_name: str = "llmops-experiments"

    # ── Cloud Monitoring ──────────────────────────────────────────────────────
    cloud_monitoring_enabled: bool = True

    # ── Vertex AI Safety / Perspective API ────────────────────────────────────
    perspective_api_key: str = ""
    perspective_threshold: float = 0.7

    # ── Cloud Memorystore / Redis ─────────────────────────────────────────────
    gcp_redis_url: str = Field(
        default="",
        validation_alias=AliasChoices("GCP_REDIS_URL", "REDIS_URL"),
    )  # redis://<ip>:6379

    # ── Cloud Composer / Dataflow ─────────────────────────────────────────────
    composer_environment: str = ""
    dataflow_temp_location: str = ""    # gs://<bucket>/tmp/


@lru_cache(maxsize=1)
def get_gcp_settings() -> GCPSettings:
    return GCPSettings()


def reset_gcp_settings() -> None:
    """Clear the settings cache — used in tests that change APP_ENV."""
    get_gcp_settings.cache_clear()
