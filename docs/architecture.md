# Build Stage Inspector Advisor Architecture

## Overview

Build Stage Inspector Advisor is an open-source RAG and agent system for
construction-stage inspection advice. The runtime is OSS-first: FastAPI,
LiteLLM, Qdrant, Redis, MLflow, OpenTelemetry, Prometheus, Grafana, Jaeger,
LangGraph, CrewAI, and optional S3-compatible object storage.

Cloud platforms are not runtime targets. They can still be data sources through
connectors, such as object storage, SharePoint, SQL systems, streams, web pages,
or query-time web search.

## Target Flow

```text
local/cloud/sharepoint/web sources
  -> source connectors
  -> data lineage
  -> cleaner + PII handling
  -> chunker + metadata enrichment
  -> Qdrant vector index
  -> RAG retriever + optional filters/rerankers
  -> LiteLLM model route
  -> FastAPI gateway / agents
  -> audit, metrics, traces, evals, feedback
  -> Streamlit UI for user interaction
```

## Best-Practice OSS Service Architecture

| Layer | Service | Local URL | Staging/production URL to create |
|---|---|---|---|
| Public gateway | FastAPI app | `http://localhost:4000` | `https://advisor.<domain>` |
| LLM routing | LiteLLM | `http://localhost:4000` in Compose, or separate from app when deployed | `https://litellm.<domain>` or internal `http://litellm:4000` |
| Vector database | Qdrant Cloud | `https://fe4f808f-27d6-4bdd-b403-482c42926700.europe-west6-0.gcp.cloud.qdrant.io:6333/dashboard` | `https://fe4f808f-27d6-4bdd-b403-482c42926700.europe-west6-0.gcp.cloud.qdrant.io:6333` |
| Cache/rate limit | Redis | `redis://localhost:6379` in test stack | `redis://redis.<domain>:6379` or private service DNS |
| Object store | S3-compatible store / MinIO / LocalStack | `http://localhost:4566` in test stack | `https://objects.<domain>` or private object-store endpoint |
| Experiment tracking | MLflow | `http://localhost:5000` | `https://mlflow.<domain>` |
| Prompt/trace review | Langfuse, optional | not currently composed | `https://langfuse.<domain>` or hosted Langfuse URL |
| Metrics | Prometheus | `http://localhost:9090` | `https://prometheus.<domain>` or private service |
| Dashboards | Grafana | `http://localhost:3000` | `https://grafana.<domain>` |
| Tracing | Jaeger UI | `http://localhost:16686` | `https://jaeger.<domain>` |
| OTLP collector | Jaeger/OTel endpoint | `http://localhost:4317` and `http://localhost:4318` | `https://otel.<domain>:4317` or private collector |
| Streams | Kafka | `localhost:9092` | `kafka.<domain>:9092` or private broker |

For production, expose only the public advisor gateway and approved dashboards.
Keep Qdrant, Redis, object storage, Kafka, MLflow backend stores, and OTLP
collectors private unless there is a deliberate admin access path.

## Credentials And Secrets To Obtain

| Area | Required secret or credential | Notes |
|---|---|---|
| LLM providers | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, optional local model route key | Use LiteLLM routes and model fallbacks; keep provider keys out of docs and source |
| LiteLLM | `LITELLM_MASTER_KEY` | Required for gateway access control when LiteLLM is exposed |
| Qdrant | `QDRANT_URL`, `QDRANT_API_KEY` | Use the Qdrant Cloud URL above. Store the API key only in `.env.development`, deployment secrets, or a secret manager |
| Redis | `REDIS_URL` with password if secured | Used for semantic cache and rate-limit state |
| Object storage | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_ENDPOINT_URL`, `S3_BUCKET` | Treat as S3-compatible storage credentials, not a cloud deployment target |
| MLflow | `MLFLOW_TRACKING_URI`, backend DB credentials if externalized | Use a persistent backend store and artifact store outside local demos |
| W&B, optional | `WANDB_API_KEY`, `WANDB_PROJECT` | Optional experiment tracking supplement |
| Langfuse, optional | `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` | Prompt/trace review and callbacks |
| SharePoint / Microsoft 365 source | Tenant ID, client ID, client secret or certificate, site/library IDs | Needed only when SharePoint ingestion is implemented |
| Web search source | Chosen web-search API key and allowed domains policy | Needed only for query-time or scheduled web ingestion |
| SQL sources | DSN, read-only username/password, TLS config | Use read-only credentials and source-specific schemas |
| Gateway auth | JWT/OIDC issuer, audience, JWKS URL, admin users/groups | Replace header-based identity before production |
| Dashboard admin | Grafana admin password or SSO config | Rotate defaults immediately outside local development |

Store production values in a secret manager or deployment secret store. The
`.env.*.example` files document names only and must not contain real values.

## Data Ingestion

| Component | File | Purpose |
|---|---|---|
| Base connector | `data_ingestion/sources/base.py` | Common `RawDocument` contract |
| File connector | `data_ingestion/sources/file_connector.py` | PDF, HTML, Markdown, and text from local folders and S3-compatible storage |
| SQL connector | `data_ingestion/sources/sql_connector.py` | Structured database ingestion |
| Stream connector | `data_ingestion/sources/stream_connector.py` | Event ingestion through Kafka |
| Cleaner | `data_ingestion/etl/cleaner.py` | Text normalization and PII handling |
| Chunker | `data_ingestion/chunking/chunker.py` | Fixed-token and sentence chunking |
| Metadata enrichment | `data_ingestion/enrichment/documents.py` | Canonical document metadata for NCC, contracts, policies, legal material, web, and SharePoint sources |

Primary ingestion starts from `data/raw_docs`. Future source connectors should
preserve the same downstream contract and add metadata needed for citations,
filtering, trust scoring, and ACL checks.

Recommended document metadata:

```text
document_type, source_type, source_uri, source_title, source_version,
retrieved_at, document_family, jurisdiction, effective_date, section, clause,
volume, building_class, inspection_stage, project_id, contract_id, tenant_id,
acl_user_ids, acl_group_ids, trust_level, tags
```

Use `document_type` to keep heterogeneous corpora filterable. Initial values are
`regulation`, `contract`, `policy`, `legal`, `standard`, `guidance`, `report`,
`web`, and `other`.

## Storage And Retrieval

Qdrant is the primary vector store. Use one collection per environment or tenant
boundary unless there is a clear reason to share collections.

Configured Qdrant Cloud endpoint:

```text
QDRANT_URL=https://fe4f808f-27d6-4bdd-b403-482c42926700.europe-west6-0.gcp.cloud.qdrant.io:6333
```

Keep `QDRANT_API_KEY` out of tracked files. Put it in `.env.development` for
local work and in deployment secrets for staging/production.

Recommended collection naming:

```text
buildstage_documents_development
buildstage_documents_staging
buildstage_documents_production
```

Override with `QDRANT_COLLECTION_NAME` when a deployment needs a tenant-specific
or migration-specific collection.

RAG settings:

| Variable | Recommended starting value | Production guidance |
|---|---|---|
| `RAG_RETRIEVAL_MODE` | `vector` | Move to `hybrid` when keyword precision matters |
| `RAG_SECURITY_MODE` | `metadata_filtering` | Use `acl_filtering` or `policy_enforced_acl` for private project/contract docs |
| `GRAPH_ENABLED` | `false` | Enable only after a graph adapter exists |
| `RERANKER_ENABLED` | `false` | Enable after adding deterministic reranker evals |

For private contracts and project files, enforce ACLs before or during
retrieval. Do not rely on post-retrieval filtering for sensitive documents.

## Serving

The public application service is `serving.gateway.app:app` on port `4000`.
Best-practice production deployment:

- Run at least two replicas.
- Put TLS termination and auth at the edge.
- Keep LiteLLM, Qdrant, Redis, object storage, and tracing endpoints private.
- Use health checks on `/health`.
- Export metrics on the configured metrics port before enabling Prometheus scraping.
- Set request, token, and cost budgets per team.

Use LiteLLM for model routing and fallback. The default model routes live in
`config/litellm_config.yaml`.

Key API paths:

```text
GET  /health
POST /v1/chat/completions
POST /v1/agents/run
```

The agent endpoint calls the open-source agent runner, whose
`search_knowledge_base` tool invokes `POST /v1/rag/query` over HTTP. The RAG
endpoint owns the Qdrant-backed pipeline through `serving/rag/service.py`, so
agent orchestration and retrieval can be deployed as separate REST-facing
microservices.

## Observability

Use OpenTelemetry traces, Prometheus metrics, Grafana dashboards, and Jaeger
for trace inspection.

Minimum production signals:

- Request count and error rate
- P50/P95/P99 latency
- Retrieval latency and retrieved chunk count
- Token usage and estimated cost
- Cache hit rate
- Guardrail blocks and output redactions
- RAG faithfulness and drift reports
- Unauthorized retrieval attempts

## Governance

Keep these gates before production:

- Real gateway auth through JWT/OIDC, not trusted headers
- Role and team policy checks in `governance/access_control`
- Tamper-evident audit logs
- Cost budgets by team/project
- Safety evals and regression evals
- ACL leakage tests for private corpora
- Human review before prompt/model changes promote

## Local Development

Start the full local stack:

```bash
docker compose up -d
uvicorn serving.gateway.app:app --port 4000
```

Run the default test suite:

```bash
python -m pytest -q
```

Start the lightweight test stack when testing Redis, Qdrant, LocalStack, or
WireMock integrations:

```bash
docker compose -f docker-compose.test.yml up -d
```

## Adding A New Data Source

1. Create `data_ingestion/sources/my_source_connector.py`.
2. Subclass `BaseSourceConnector`.
3. Implement `validate_connection()` and `fetch()`.
4. Register the source in `scripts/run_ingestion.py` or a future source registry.
5. Add source metadata for citations, filters, trust level, and ACL enforcement.
6. Add a fixture-backed ingestion test and a retrieval leakage test when the source can contain private records.

## Adding A New Eval Metric

1. Add the metric to `model_development/evaluation/eval_harness.py`.
2. Add thresholds to `scripts/run_evals.py`.
3. Update the relevant CI/CD gate under `governance/cicd/`.
4. Require a project-specific golden dataset before treating the gate as production-ready.
