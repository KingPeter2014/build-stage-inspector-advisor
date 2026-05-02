# Open-Source Use-Case Finalization Template

Use this when a concrete project chooses the open-source stack.

## Required Inputs

- Business goal and success metric:
- User groups, tenants, and access model:
- Data sources and refresh frequency:
- Corpus sensitivity:
- RAG retrieval mode: `vector` / `hybrid` / `graph_augmented` / `hybrid_graph`
- RAG security mode: `none` / `metadata_filtering` / `acl_filtering` / `policy_enforced_acl`
- Graph database choice, if any: Neo4j / ArangoDB / Memgraph / other
- Keyword search backend for hybrid, if any: Qdrant hybrid / OpenSearch / Elasticsearch
- LLM provider: OpenAI / Anthropic / local model / LiteLLM route
- Eval datasets and thresholds:
- Latency and cost SLOs:
- Deployment target: Docker Compose / Kubernetes / managed Kubernetes

## Finalization Instructions

1. Set `APP_PROVIDER=open_source` and choose `APP_COMPLEXITY`.
2. Configure Qdrant collection naming, embedding model, vector dimension, and metadata schema.
3. If `RAG_RETRIEVAL_MODE=hybrid`, implement or enable `search_hybrid` on the retriever backend.
4. If graph mode is selected, add a graph adapter exposing `search_graph_augmented`.
5. If ACL filtering is required, map users/groups/tenants to chunk metadata and enforce filters before retrieval.
6. Replace reference eval stubs with project golden datasets and retrieval leakage tests.
7. Configure LiteLLM model routes, budgets, and fallback behavior.
8. Configure observability: OpenTelemetry, Prometheus, Grafana, Langfuse or equivalent.
9. Run unit, integration, eval, and smoke gates in the selected production mode.

## Production Gate Checklist

- No `status=stubbed` reports in production CI.
- Unauthorized documents cannot be retrieved.
- Golden regression and safety evals meet thresholds.
- Cost budgets and rate limits match team policies.
- Prompt/model changes require review and rollback path.
