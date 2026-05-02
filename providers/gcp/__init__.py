"""
providers/gcp — GCP Vertex AI LLMOps stack.

Stack:
  LLM Gateway        Vertex AI Model Garden (google-cloud-aiplatform)
  Vector Store       Vertex AI Vector Search (google-cloud-aiplatform)
  Data Lake          Google Cloud Storage (google-cloud-storage)
  Feature Store      Vertex AI Feature Store (google-cloud-aiplatform)
  Experiment Track.  Vertex AI Experiments (google-cloud-aiplatform)
  Model Registry     Vertex AI Model Registry (google-cloud-aiplatform)
  Single Agent       Vertex AI Agent Engine (google-cloud-aiplatform)
  Multi-Agent        Vertex AI Agent Engine multi-agent
  Observability      Cloud Monitoring + Cloud Logging (google-cloud-monitoring)
  ETL                Cloud Composer + Dataflow / Apache Beam
  Guardrails         Vertex AI Safety + Perspective API
  Auth               Google IAM + Identity Platform (google-auth)
  Caching            Cloud Memorystore for Redis (REDIS_URL env var)
"""

PROVIDER_NAME = "gcp"
