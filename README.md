# Build Stage Inspector Advisor

An open-source RAG and agent framework for construction-stage inspection advice.

The project is being adapted from a broader LLMOps reference framework into a
single open-source runtime. The primary ingestion path is local documents, but
the ingestion layer is intentionally source-extensible: future connectors may
pull from cloud object storage, SharePoint, SQL databases, streams, web pages,
or query-time web search. Those are data sources, not deployment targets.

The first concrete corpus includes building-regulation material such as NCC
documents. The project is not limited to NCC 2022; domestic building contracts,
project-specific documents, standards, web-sourced references, and future
document sets can be added through the same ingestion and retrieval pipeline.

## Runtime Target

Only the open-source runtime target is supported.

| Layer | Open-source implementation |
|---|---|
| LLM access | LiteLLM with OpenAI, Anthropic, or local/OpenAI-compatible models |
| Vector store | Qdrant |
| Retrieval | Vector RAG, with extension points for hybrid, graph, ACL filters, and reranking |
| Agents | LangGraph and CrewAI |
| Observability | OpenTelemetry, Prometheus, Grafana, Jaeger, optional Langfuse |
| Model/eval workflow | MLflow, local eval datasets, Ragas/DeepEval harnesses |
| Deployment | Docker Compose locally; Helm/Kubernetes when needed |

Azure, AWS, and GCP deployment/provider targets have been removed from this
codebase. Cloud-hosted data sources can still be added as ingestion connectors
when the project needs them.

## Repository Layout

```text
core/                         Shared contracts, schemas, RAG options, stub policy
data_ingestion/               Source connectors, cleaning, chunking
storage/                      Qdrant vector store, data lake, feature store, prompt registry
serving/                      FastAPI gateway, RAG pipeline, agents, cache, guardrails
model_development/            Experiments, fine-tuning, eval harness, model registry
observability/                Tracing, metrics, drift detection, feedback collection
governance/                   RBAC, audit logging, cost controls, CI/CD templates
providers/open_source/        OSS runtime adapter wiring
config/                       App settings, LiteLLM config, Prometheus config
docs/                         Architecture notes and use-case templates
data/raw_docs/                Local document drop zone for ingestion
tests/                        Unit, integration, eval, and smoke tests
```

## Data Sources

The current ingestion command reads local files from `data/raw_docs` by default.
Supported local formats are PDF, HTML, Markdown, and plain text.

Planned or possible source types:

- Local document folders for regulations, contracts, inspection reports, and project files
- S3-compatible object storage or other cloud storage through source connectors
- SharePoint or Microsoft 365 document libraries
- SQL databases for structured project, defect, or contract metadata
- Streams for event-style ingestion
- Web pages or web search results for query-time augmentation, subject to citation and trust rules

Each source should implement `BaseSourceConnector` and emit `RawDocument`
objects. Cleaning, chunking, indexing, retrieval, and evaluation should remain
unchanged after the connector boundary.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop
- Git

### Install Dependencies

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r providers/open_source/requirements.txt
```

### Start Local Services

```bash
docker compose up -d
```

Useful local endpoints:

- Qdrant: `http://localhost:6333/dashboard`
- MLflow: `http://localhost:5000`
- Grafana: `http://localhost:3000`
- Jaeger: `http://localhost:16686`
- LiteLLM: `http://localhost:4000`

### Ingest Documents

Place source files in `data/raw_docs`, then run:

```bash
python scripts/run_ingestion.py --source-dir data/raw_docs
```

### Run Evals

```bash
python scripts/run_evals.py --suite regression --seed
python scripts/run_evals.py --suite safety
python scripts/run_evals.py --suite rag_retrieval
```

Reference mode uses deterministic stubs for gates that do not yet have real
project data, thresholds, and fixtures. Production modes require those stubs to
be replaced.

### Start The Gateway

```bash
uvicorn serving.gateway.app:app --port 4000
```

Or build the container:

```bash
docker build -t build-stage-inspector-advisor:oss .
docker run --env-file .env.development -p 4000:4000 build-stage-inspector-advisor:oss
```

## RAG Configuration

RAG is configured through environment variables:

| Variable | Options | Purpose |
|---|---|---|
| `RAG_RETRIEVAL_MODE` | `vector`, `hybrid`, `graph_augmented`, `hybrid_graph` | Chooses retrieval strategy |
| `RAG_SECURITY_MODE` | `none`, `metadata_filtering`, `acl_filtering`, `policy_enforced_acl` | Chooses access-control posture |
| `GRAPH_ENABLED` | `true`, `false` | Required for graph-based retrieval modes |
| `RERANKER_ENABLED` | `true`, `false` | Enables reranking when implemented |

For sensitive project or contract documents, ACL constraints must be applied
before or during retrieval. Post-retrieval filtering is acceptable only for
low-risk reference corpora.

## Framework Maturity Modes

Set `APP_COMPLEXITY` to control how strict the framework should be.

| Mode | Purpose | Stub policy |
|---|---|---|
| `reference` | Local development, demos, docs, deterministic tests | Explicit stubs may pass and emit reports |
| `starter-production` | Real data, auth, secrets, evals, observability | Stubs fail gates unless replaced |
| `regulated-production` | Stronger audit, PII controls, approvals, private networking | Stubs fail gates unless replaced |

## Next Adaptation Work

The removal pass narrows the runtime target. The next project-planning pass
should define the concrete domain contracts:

- document metadata for regulations, standards, contracts, and project files
- source trust and citation policy for web-derived data
- inspection-stage taxonomy
- RAG prompts for advisory answers with clause/source references
- golden evals for building-stage advice and refusal behavior
- access-control rules for private project and contract documents
