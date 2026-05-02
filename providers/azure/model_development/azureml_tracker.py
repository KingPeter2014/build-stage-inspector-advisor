"""
providers/azure/model_development/azureml_tracker.py
Azure ML Experiments — AbstractExperimentTracker implementation.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from azure.ai.ml import MLClient
from azure.ai.ml.entities import Job
from azure.identity import DefaultAzureCredential

from core.interfaces.experiment_tracker import AbstractExperimentTracker
from providers.azure.config.settings import get_azure_settings


class AzureMLTracker(AbstractExperimentTracker):
    """
    AbstractExperimentTracker backed by Azure ML Experiments + MLflow (Azure-hosted).
    Azure ML provides a managed MLflow tracking server accessible via ml_client.
    """

    def __init__(self) -> None:
        s = get_azure_settings()
        self._client = MLClient(
            credential=DefaultAzureCredential(),
            subscription_id=s.azure_subscription_id,
            resource_group_name=s.azureml_resource_group,
            workspace_name=s.azureml_workspace_name,
        )
        # Configure MLflow to use the Azure ML tracking URI
        import mlflow
        tracking_uri = self._client.workspaces.get(s.azureml_workspace_name).mlflow_tracking_uri
        mlflow.set_tracking_uri(tracking_uri)
        self._mlflow = mlflow
        self._run = None

    @contextmanager
    def run(self, run_name: str, tags: dict[str, str] | None = None) -> Generator["AzureMLTracker", None, None]:
        with self._mlflow.start_run(run_name=run_name, tags=tags) as run:
            self._run = run
            yield self

    def log_params(self, params: dict[str, Any]) -> None:
        self._mlflow.log_params(params)

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        self._mlflow.log_metrics(metrics, step=step)

    def log_artifact(self, local_path: str, artifact_path: str | None = None) -> None:
        self._mlflow.log_artifact(local_path, artifact_path)

    def set_tag(self, key: str, value: str) -> None:
        self._mlflow.set_tag(key, value)
