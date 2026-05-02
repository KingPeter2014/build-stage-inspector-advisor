"""
providers/gcp/model_development/vertex_tracker.py
Vertex AI Experiments — AbstractExperimentTracker implementation.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from google.cloud import aiplatform

from core.interfaces.experiment_tracker import AbstractExperimentTracker
from providers.gcp.config.settings import get_gcp_settings


class VertexExperimentTracker(AbstractExperimentTracker):
    """AbstractExperimentTracker backed by Vertex AI Experiments."""

    def __init__(self) -> None:
        s = get_gcp_settings()
        aiplatform.init(
            project=s.gcp_project_id,
            location=s.gcp_region,
            experiment=s.vertex_experiment_name,
        )
        self._run_ctx = None

    @contextmanager
    def run(self, run_name: str, tags: dict[str, str] | None = None) -> Generator["VertexExperimentTracker", None, None]:
        with aiplatform.start_run(run_name) as run:
            self._run_ctx = run
            if tags:
                for k, v in tags.items():
                    aiplatform.log_params({k: v})
            yield self
        self._run_ctx = None

    def log_params(self, params: dict[str, Any]) -> None:
        aiplatform.log_params(params)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        aiplatform.log_metrics(metrics)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        # Upload to GCS then log as Vertex Artifact
        from google.cloud import storage
        s = get_gcp_settings()
        gcs_uri = f"gs://{s.gcs_bucket}/artifacts/{artifact_path or local_path}"
        storage.Client(project=s.gcp_project_id).bucket(s.gcs_bucket).blob(
            f"artifacts/{artifact_path or local_path}"
        ).upload_from_filename(local_path)
        aiplatform.log_params({"artifact_uri": gcs_uri})

    def set_tag(self, key: str, value: str) -> None:
        aiplatform.log_params({key: value})
