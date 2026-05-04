# Open-Source Use-Case Finalization Template

Use this when a concrete project chooses the open-source stack.

## Required Inputs

- Business goal and success metric:
- User groups, tenants, and access model:
- Data sources and refresh frequency:
- Document types to ingest: `regulation` / `contract` / `policy` / `legal` / `standard` / `guidance` / `report` / `web` / `other`
- Inspection stages to support: `site_prep` / `slab` / `frame` / `lockup` / `waterproofing` / `fixing` / `practical_completion` / `handover` / `other`
- Domain filters to expose: `document_type` / `inspection_stage` / `jurisdiction` / `building_class` / `tenant_id` / `project_id` / `contract_id`
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
2. Configure Qdrant collection naming, embedding model, vector dimension, and metadata schema, including `document_type`, `inspection_stage`, `jurisdiction`, `building_class`, and source citation fields.
3. If `RAG_RETRIEVAL_MODE=hybrid`, implement or enable `search_hybrid` on the retriever backend.
4. If graph mode is selected, add a graph adapter exposing `search_graph_augmented`.
5. If ACL filtering is required, map users/groups/tenants to chunk metadata and enforce filters before retrieval.
6. Replace reference eval stubs with project golden datasets covering grounded NCC answers, missing-evidence refusals, contract-specific answers, source conflicts, unsafe/legal overreach refusals, and ACL leakage tests.
7. Configure LiteLLM model routes, budgets, and fallback behavior.
8. Configure observability: OpenTelemetry, Prometheus, Grafana, Langfuse or equivalent.
9. Run unit, integration, eval, and smoke gates in the selected production mode.

## Production Gate Checklist

- No `status=stubbed` reports in production CI.
- Unauthorized documents cannot be retrieved.
- Agent endpoint can call the RAG knowledge-base tool and cites retrieved sources.
- RAG answers cite `source_title` plus clause, section, or volume when available.
- Golden regression and safety evals meet thresholds.
- Cost budgets and rate limits match team policies.
- Prompt/model changes require review and rollback path.
