"""
providers/gcp/model_development/vertex_registry.py
Vertex AI Model Registry — AbstractModelRegistry implementation.
"""
from __future__ import annotations

from google.cloud import aiplatform

from core.interfaces.model_registry import AbstractModelRegistry, ModelCard, ModelStage
from providers.gcp.config.settings import get_gcp_settings

_STAGE_LABEL = {
    ModelStage.STAGING: "staging",
    ModelStage.PRODUCTION: "production",
    ModelStage.ARCHIVED: "archived",
    ModelStage.CHALLENGER: "challenger",
}


class VertexModelRegistry(AbstractModelRegistry):
    """
    AbstractModelRegistry backed by Vertex AI Model Registry.
    Models are uploaded as Vertex AI Model resources with labels for stage.
    """

    def __init__(self) -> None:
        s = get_gcp_settings()
        aiplatform.init(project=s.gcp_project_id, location=s.gcp_region)

    def register(self, run_id: str, model_name: str, artifact_path: str = "model") -> ModelCard:
        s = get_gcp_settings()
        model = aiplatform.Model.upload(
            display_name=model_name,
            artifact_uri=f"gs://{s.gcs_bucket}/models/{run_id}/{artifact_path}",
            serving_container_image_uri="us-docker.pkg.dev/vertex-ai/prediction/sklearn-cpu.1-3:latest",
            labels={"stage": ModelStage.STAGING.value, "run_id": run_id[:63]},
        )
        return ModelCard(
            model_name=model_name,
            version=model.resource_name.split("/")[-1],
            stage=ModelStage.STAGING,
            tags={"resource_name": model.resource_name},
        )

    def promote(self, model_name: str, version: str, stage: ModelStage) -> None:
        # Vertex AI doesn't have a native stage concept; use labels
        models = aiplatform.Model.list(filter=f'display_name="{model_name}"')
        for model in models:
            if model.resource_name.endswith(f"/{version}"):
                model.update(labels={**model.labels, "stage": _STAGE_LABEL[stage]})
                return

    def get_champion(self, model_name: str) -> ModelCard | None:
        models = aiplatform.Model.list(
            filter=f'display_name="{model_name}" AND labels.stage="production"',
            order_by="create_time desc",
        )
        if not models:
            return None
        m = models[0]
        return ModelCard(
            model_name=model_name,
            version=m.resource_name.split("/")[-1],
            stage=ModelStage.PRODUCTION,
            tags=dict(m.labels or {}),
        )

    def list_versions(self, model_name: str) -> list[ModelCard]:
        models = aiplatform.Model.list(filter=f'display_name="{model_name}"')
        return [
            ModelCard(
                model_name=model_name,
                version=m.resource_name.split("/")[-1],
                stage=ModelStage((m.labels or {}).get("stage", "staging")),
                tags=dict(m.labels or {}),
            )
            for m in models
        ]

    def archive(self, model_name: str, version: str) -> None:
        self.promote(model_name, version, ModelStage.ARCHIVED)
