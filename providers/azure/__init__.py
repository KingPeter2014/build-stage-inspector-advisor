"""
providers/azure — Azure AI Foundry LLMOps stack.

Stack:
  LLM Gateway        Azure OpenAI Service  (azure-ai-inference)
  Vector Store       Azure AI Search       (azure-search-documents)
  Data Lake          Azure Blob / ADLS Gen2 (azure-storage-blob)
  Feature Store      Azure ML Feature Store (azure-ai-ml)
  Experiment Track.  Azure ML Experiments  (azure-ai-ml)
  Model Registry     Azure ML Model Registry (azure-ai-ml)
  Single Agent       Azure AI Foundry Agent (azure-ai-projects)
  Multi-Agent        Azure AI Foundry Multi-Agent (azure-ai-projects)
  Observability      Azure Monitor + App Insights (azure-monitor-opentelemetry-exporter)
  ETL                Azure Data Factory    (azure-mgmt-datafactory)
  Guardrails         Azure Content Safety  (azure-ai-contentsafety)
  Auth               Azure Entra ID        (azure-identity)
  Caching            Azure Cache for Redis (redis-py + AZURE_REDIS_URL)
"""

PROVIDER_NAME = "azure"
