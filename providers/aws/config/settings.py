"""
providers/aws/config/settings.py
AWS-specific environment configuration.

Load order (later overrides earlier):
  1. .env
  2. .env.<APP_ENV>  (e.g. .env.staging, .env.production)
  3. actual environment variables (highest priority — used in CI and ECS runtime)

In production, aws_access_key_id / aws_secret_access_key must be empty:
use the ECS task IAM role instead.
"""
from __future__ import annotations

import os
import warnings
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.getenv("APP_ENV", "development")


class AWSSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_APP_ENV}"),
        extra="ignore",
    )

    @model_validator(mode="after")
    def _warn_prod_static_credentials(self) -> "AWSSettings":
        if _APP_ENV == "production" and (self.aws_access_key_id or self.aws_secret_access_key):
            warnings.warn(
                "Static AWS credentials (aws_access_key_id / aws_secret_access_key) are set "
                "in production. Use the ECS task IAM role instead — remove these from your config.",
                stacklevel=2,
            )
        return self

    # ── AWS Identity ──────────────────────────────────────────────────────────
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""         # Use IAM roles / instance profiles in production
    aws_secret_access_key: str = ""
    aws_session_token: str = ""

    # ── Amazon Bedrock ────────────────────────────────────────────────────────
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_embedding_model_id: str = "amazon.titan-embed-text-v2:0"
    bedrock_guardrail_id: str = ""      # Created in Bedrock console
    bedrock_guardrail_version: str = "DRAFT"

    # ── AWS AgentCore / Bedrock Agents ────────────────────────────────────────
    bedrock_agent_id: str = ""
    bedrock_agent_alias_id: str = "TSTALIASID"
    agentcore_endpoint_url: str = ""    # Optional custom AgentCore endpoint

    # ── Amazon OpenSearch ─────────────────────────────────────────────────────
    opensearch_endpoint: str = ""       # https://<domain>.es.amazonaws.com
    opensearch_index: str = "llmops-index"

    # ── Amazon S3 ─────────────────────────────────────────────────────────────
    s3_bucket: str = Field(
        default="llmops-data",
        validation_alias=AliasChoices("S3_BUCKET", "S3_BUCKET_NAME"),
    )
    s3_prefix: str = "llmops"

    # ── Amazon SageMaker ──────────────────────────────────────────────────────
    sagemaker_role_arn: str = ""        # arn:aws:iam::<account>:role/SageMakerRole
    sagemaker_experiment_name: str = "llmops-experiments"
    sagemaker_model_package_group: str = "llmops-models"

    # ── Amazon CloudWatch ─────────────────────────────────────────────────────
    cloudwatch_namespace: str = "LLMOps"
    xray_enabled: bool = True

    # ── Amazon ElastiCache for Redis ──────────────────────────────────────────
    aws_redis_url: str = Field(
        default="",
        validation_alias=AliasChoices("AWS_REDIS_URL", "REDIS_URL"),
    )  # redis://<host>:6379

    # ── AWS Glue ──────────────────────────────────────────────────────────────
    glue_database: str = "llmops_db"
    glue_crawler_name: str = "llmops-crawler"


@lru_cache(maxsize=1)
def get_aws_settings() -> AWSSettings:
    return AWSSettings()


def reset_aws_settings() -> None:
    """Clear the settings cache — used in tests that change APP_ENV."""
    get_aws_settings.cache_clear()
