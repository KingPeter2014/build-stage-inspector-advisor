"""
providers/aws/model_development/sagemaker_registry.py
Amazon SageMaker Model Registry — AbstractModelRegistry implementation.
"""
from __future__ import annotations

import boto3

from core.interfaces.model_registry import AbstractModelRegistry, ModelCard, ModelStage
from providers.aws.config.settings import get_aws_settings

_STAGE_MAP = {
    ModelStage.STAGING: "PendingManualApproval",
    ModelStage.PRODUCTION: "Approved",
    ModelStage.ARCHIVED: "Rejected",
    ModelStage.CHALLENGER: "PendingManualApproval",
}
_REVERSE_STAGE = {v: k for k, v in _STAGE_MAP.items()}


class SageMakerRegistry(AbstractModelRegistry):
    """
    AbstractModelRegistry backed by Amazon SageMaker Model Registry
    (Model Package Groups + Model Packages).
    """

    def __init__(self) -> None:
        s = get_aws_settings()
        self._sm = boto3.client("sagemaker", region_name=s.aws_region)
        self._package_group = s.sagemaker_model_package_group
        self._ensure_group()

    def _ensure_group(self) -> None:
        try:
            self._sm.describe_model_package_group(ModelPackageGroupName=self._package_group)
        except self._sm.exceptions.ClientError:
            self._sm.create_model_package_group(
                ModelPackageGroupName=self._package_group,
                ModelPackageGroupDescription="LLMOps model registry",
            )

    def register(self, run_id: str, model_name: str, artifact_path: str = "model") -> ModelCard:
        resp = self._sm.create_model_package(
            ModelPackageGroupName=self._package_group,
            ModelPackageDescription=f"Run {run_id}",
            ModelApprovalStatus="PendingManualApproval",
            Tags=[{"Key": "run_id", "Value": run_id}, {"Key": "model_name", "Value": model_name}],
        )
        arn = resp["ModelPackageArn"]
        version = arn.split("/")[-1]
        return ModelCard(model_name=model_name, version=version, stage=ModelStage.STAGING,
                         tags={"run_id": run_id})

    def promote(self, model_name: str, version: str, stage: ModelStage) -> None:
        arn = f"arn:aws:sagemaker:{get_aws_settings().aws_region}::model-package/{self._package_group}/{version}"
        self._sm.update_model_package(
            ModelPackageArn=arn,
            ModelApprovalStatus=_STAGE_MAP.get(stage, "PendingManualApproval"),
        )

    def get_champion(self, model_name: str) -> ModelCard | None:
        packages = self._sm.list_model_packages(
            ModelPackageGroupName=self._package_group,
            ModelApprovalStatus="Approved",
            SortBy="CreationTime",
            SortOrder="Descending",
            MaxResults=1,
        ).get("ModelPackageSummaryList", [])
        if not packages:
            return None
        p = packages[0]
        version = p["ModelPackageArn"].split("/")[-1]
        return ModelCard(model_name=model_name, version=version, stage=ModelStage.PRODUCTION)

    def list_versions(self, model_name: str) -> list[ModelCard]:
        packages = self._sm.list_model_packages(
            ModelPackageGroupName=self._package_group,
        ).get("ModelPackageSummaryList", [])
        return [
            ModelCard(
                model_name=model_name,
                version=p["ModelPackageArn"].split("/")[-1],
                stage=_REVERSE_STAGE.get(p["ModelApprovalStatus"], ModelStage.STAGING),
            )
            for p in packages
        ]

    def archive(self, model_name: str, version: str) -> None:
        self.promote(model_name, version, ModelStage.ARCHIVED)
