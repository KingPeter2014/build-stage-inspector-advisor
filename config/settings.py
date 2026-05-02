"""
config/settings.py
Centralised settings loaded from environment variables via pydantic-settings.

Load order (later files override earlier ones):
  1. .env                   — base defaults
  2. .env.<APP_ENV>         — environment-specific overrides (dev / staging / prod)
  3. actual environment variables — highest priority (CI/CD injected values)
"""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

_APP_ENV = os.getenv("APP_ENV", "development")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{_APP_ENV}"),
        extra="ignore",
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    default_model: str = "gpt-4o"
    max_tokens: int = 4096

    # LLM providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    huggingface_token: str = ""

    # Vector store
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    pgvector_dsn: str = ""

    # Object store
    s3_bucket: str = "llmops-data-lake"
    aws_default_region: str = "us-east-1"

    # Prompt registry / observability
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # Experiment tracking
    mlflow_tracking_uri: str = "http://localhost:5000"
    wandb_project: str = "llmops-experiments"

    # OpenTelemetry
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "llmops-service"

    # LiteLLM gateway
    litellm_master_key: str = ""
    litellm_port: int = 4000

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_ingestion: str = "llmops.ingestion"

    # RAG behavior
    rag_retrieval_mode: str = "vector"
    rag_security_mode: str = "none"
    graph_enabled: bool = False
    reranker_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
