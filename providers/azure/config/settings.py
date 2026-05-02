"""
providers/azure/config/settings.py
Azure-specific environment configuration.

Load order (later overrides earlier):
  1. .env
  2. .env.<APP_ENV>  (e.g. .env.staging, .env.production)
  3. actual environment variables (highest priority — used in CI and cloud runtime)

In production, azure_client_secret must be empty: use Managed Identity instead.
"""
from __future__ import annotations

import os
import warnings
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.getenv("APP_ENV", "development")


class AzureSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_APP_ENV}"),
        extra="ignore",
    )

    @model_validator(mode="after")
    def _warn_prod_client_secret(self) -> "AzureSettings":
        if _APP_ENV == "production" and self.azure_client_secret:
            warnings.warn(
                "azure_client_secret is set in production. "
                "Use Managed Identity instead — remove AZURE_CLIENT_SECRET from your config.",
                stacklevel=2,
            )
        return self

    # ── Identity ──────────────────────────────────────────────────────────────
    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""          # Use managed identity in production

    # ── Azure OpenAI ──────────────────────────────────────────────────────────
    azure_openai_endpoint: str = ""        # https://<resource>.openai.azure.com/
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment_name: str = "gpt-4o"

    # ── Azure AI Foundry / AI Projects ────────────────────────────────────────
    azure_ai_project_connection_string: str = ""  # from AI Foundry portal
    azure_ai_project_name: str = ""
    azure_ai_hub_name: str = ""
    azure_subscription_id: str = ""
    azure_resource_group: str = ""

    # ── Azure AI Search ───────────────────────────────────────────────────────
    azure_search_endpoint: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_SEARCH_ENDPOINT", "AZURE_AI_SEARCH_ENDPOINT"),
    )  # https://<resource>.search.windows.net
    azure_search_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_SEARCH_API_KEY", "AZURE_AI_SEARCH_API_KEY"),
    )
    azure_search_index_name: str = "llmops-index"

    # ── Azure Blob / ADLS Gen2 ────────────────────────────────────────────────
    azure_storage_account_name: str = ""
    azure_storage_account_key: str = ""
    azure_storage_container: str = "llmops-data"
    azure_storage_connection_string: str = ""

    # ── Azure ML Workspace ────────────────────────────────────────────────────
    azureml_workspace_name: str = ""
    azureml_resource_group: str = ""

    # ── Azure Monitor / App Insights ──────────────────────────────────────────
    azure_appinsights_connection_string: str = Field(
        default="",
        validation_alias=AliasChoices(
            "AZURE_APPINSIGHTS_CONNECTION_STRING",
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
        ),
    )
    azure_log_analytics_workspace_id: str = ""

    # ── Azure Content Safety ──────────────────────────────────────────────────
    azure_content_safety_endpoint: str = ""
    azure_content_safety_key: str = ""

    # ── Azure Cache for Redis ─────────────────────────────────────────────────
    azure_redis_url: str = Field(
        default="",
        validation_alias=AliasChoices("AZURE_REDIS_URL", "REDIS_URL"),
    )  # rediss://<host>:6380 (TLS)

    # ── Azure Data Factory ────────────────────────────────────────────────────
    azure_data_factory_name: str = ""
    azure_data_factory_resource_group: str = ""


@lru_cache(maxsize=1)
def get_azure_settings() -> AzureSettings:
    return AzureSettings()


def reset_azure_settings() -> None:
    """Clear the settings cache — used in tests that change APP_ENV."""
    get_azure_settings.cache_clear()
