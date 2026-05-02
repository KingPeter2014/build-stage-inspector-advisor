"""
providers/azure/model_development/azureml_registry.py
Azure ML Model Registry — AbstractModelRegistry implementation.
"""
from __future__ import annotations

from azure.ai.ml import MLClient
from azure.ai.ml.entities import Model
from azure.identity import DefaultAzureCredential

from core.interfaces.model_registry import AbstractModelRegistry, ModelCard, ModelStage
from providers.azure.config.settings import get_azure_settings

# Azure ML stage labels
_STAGE_MAP = {
    ModelStage.STAGING: "Staging",
    ModelStage.PRODUCTION: "Production",
    ModelStage.ARCHIVED: "Archived",
    ModelStage.CHALLENGER: "Challenger",
}


class AzureMLRegistry(AbstractModelRegistry):
    """
    AbstractModelRegistry backed by Azure ML Model Registry.
    Models are registered as Azure ML Model assets with tags for stage.
    """

    def __init__(self) -> None:
        s = get_azure_settings()
        self._client = MLClient(
            credential=DefaultAzureCredential(),
            subscription_id=s.azure_subscription_id,
            resource_group_name=s.azureml_resource_group,
            workspace_name=s.azureml_workspace_name,
        )

    def register(self, run_id: str, model_name: str, artifact_path: str = "model") -> ModelCard:
        model = Model(
            name=model_name,
            path=f"runs:/{run_id}/{artifact_path}",
            description=f"Registered from run {run_id}",
            tags={"stage": ModelStage.STAGING.value, "run_id": run_id},
        )
        registered = self._client.models.create_or_update(model)
        return ModelCard(
            model_name=registered.name,
            version=str(registered.version),
            stage=ModelStage.STAGING,
            tags=registered.tags or {},
        )

    def promote(self, model_name: str, version: str, stage: ModelStage) -> None:
        model = self._client.models.get(name=model_name, version=version)
        model.tags = {**(model.tags or {}), "stage": stage.value}
        self._client.models.create_or_update(model)

    def get_champion(self, model_name: str) -> ModelCard | None:
        for model in self._client.models.list(name=model_name):
            if (model.tags or {}).get("stage") == ModelStage.PRODUCTION.value:
                return ModelCard(
                    model_name=model.name,
                    version=str(model.version),
                    stage=ModelStage.PRODUCTION,
                    tags=model.tags or {},
                )
        return None

    def list_versions(self, model_name: str) -> list[ModelCard]:
        return [
            ModelCard(
                model_name=m.name,
                version=str(m.version),
                stage=ModelStage((m.tags or {}).get("stage", "staging")),
                tags=m.tags or {},
            )
            for m in self._client.models.list(name=model_name)
        ]

    def archive(self, model_name: str, version: str) -> None:
        self.promote(model_name, version, ModelStage.ARCHIVED)
