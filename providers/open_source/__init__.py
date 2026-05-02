"""
providers/open_source
Open-source LLMOps stack.

Stack:
  LLM Gateway        LiteLLM + FastAPI
  Vector Store       Qdrant + sentence-transformers
  Feature Store      Feast
  Data Lake          S3 / MinIO (boto3)
  Experiment Track.  MLflow + Weights & Biases
  Model Registry     MLflow Model Registry
  Fine-tuning        HuggingFace PEFT (LoRA / QLoRA) + TRL
  Single Agent       LangGraph ReAct
  Multi-Agent        CrewAI crew + LangGraph Supervisor
  Observability      OpenTelemetry → Jaeger · Prometheus · Langfuse · Grafana
  ETL                Airflow · pandas · bs4 · pypdf
  Guardrails         NeMo Guardrails + custom rule engine
  Caching            Redis + semantic cache (sentence-transformers)
  Deployment         Docker Compose · Kubernetes (Helm)

Root-level modules are the canonical implementations; this package wires them
to core/ interfaces and provides provider-scoped entry points.
"""

PROVIDER_NAME = "open_source"
