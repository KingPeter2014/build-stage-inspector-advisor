"""
providers — one sub-package per deployment target.

  providers/open_source/  — Qdrant · LiteLLM · MLflow · LangGraph · CrewAI · Prometheus
  providers/azure/        — Azure AI Foundry · Azure OpenAI · Azure ML · Azure Monitor
  providers/aws/          — Amazon Bedrock · AWS AgentCore · SageMaker · CloudWatch
  providers/gcp/          — Vertex AI · GCS · Cloud Monitoring · Agent Engine

Import rule: provider packages import from core/ and root governance/ only.
             They never import from each other.
"""

SUPPORTED_PROVIDERS = ["open_source", "azure", "aws", "gcp"]
