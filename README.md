# LLMOps Reference Framework

This is a multi-cloud plus open-source LLMOps framework that enables you to deliver a complete pipeline —
data ingestion → storage → model development → serving → observability → governance. It considers
four deployment targets from a single codebase: open-source, AWS, Azure and GCP.

> **Pick your stack, fill in your credentials, wire your data sources, and ship.**

> **Current positioning:** this repository is a reference framework with production
> paths, not a fully project-specific deployment. Production readiness requires
> real data, business evals, identity, secrets, networking, and compliance choices.
> Intentional stubs are allowed only when they are explicit and safe.

---

## Deployment Targets

| Stack | LLM | Vector Store | Agents | Observability | Compute |
|---|---|---|---|---|---|
| **Open Source** | LiteLLM (OpenAI / Anthropic / local) | Qdrant | LangGraph + CrewAI | OTel + Prometheus + Langfuse | Kubernetes (Helm) |
| **Azure AI Foundry** | Azure OpenAI Service | Azure AI Search | Azure AI Foundry Agents | Azure Monitor + App Insights | Azure Container Apps |
| **AWS AgentCore** | Amazon Bedrock (Claude / Titan / Llama) | Amazon OpenSearch | AWS AgentCore + Bedrock Agents | CloudWatch + X-Ray | ECS Fargate |
| **GCP Vertex AI** | Vertex AI Model Garden (Gemini) | Vertex AI Vector Search | Vertex AI Agent Engine | Cloud Monitoring + Cloud Trace | Cloud Run |

---

## Repository Layout

```
llmops_project/
│
├── core/                              # Shared contract layer — zero cloud SDKs
│   ├── interfaces/                    # Abstract base classes for every component
│   │   ├── llm_gateway.py             #   AbstractLLMGateway
│   │   ├── vector_store.py            #   AbstractVectorStore
│   │   ├── data_lake.py               #   AbstractDataLake
│   │   ├── feature_store.py           #   AbstractFeatureStore
│   │   ├── experiment_tracker.py      #   AbstractExperimentTracker
│   │   ├── model_registry.py          #   AbstractModelRegistry
│   │   ├── agent_runner.py            #   AbstractAgentRunner (single + multi)
│   │   └── observability.py           #   AbstractTracer, AbstractMetricsEmitter
│   └── schemas/                       # Shared Pydantic request/response models
│       ├── chat.py                    #   ChatRequest, ChatResponse, UsageInfo
│       ├── agent.py                   #   AgentInput, AgentOutput
│       └── evaluation.py             #   EvalMetrics, EvalResult
│
├── .github/
│   └── workflows/                     # GitHub Actions workflows (canonical location)
│       ├── deploy_azure.yml           #   Azure staging deploy (triggers on push to main)
│       ├── deploy_aws.yml             #   AWS staging deploy (triggers on push to main)
│       ├── deploy_gcp.yml             #   GCP staging deploy (triggers on push to main)
│       ├── promote_to_production.yml  #   Gated production promotion (tag push / manual)
│       ├── model_cicd.yml             #   Model build → eval → canary → promote
│       ├── rag_cicd.yml               #   RAG retrieval + Ragas eval → re-index
│       └── prompt_cicd.yml            #   Prompt lint → eval → registry push
│
├── governance/                        # Shared across ALL providers — no cloud SDKs
│   ├── access_control/rbac.py         #   Role-based access control
│   ├── audit/audit_logger.py          #   Tamper-evident audit logging (SHA-256)
│   ├── cost/cost_manager.py           #   Per-team budget policies + cost ledger
│   └── cicd/                          #   Reference copies of .github/workflows/ YAMLs
│
├── serving/                           # Shared serving utilities
│   ├── cache/semantic_cache.py        #   Two-level cache: SHA-256 + cosine similarity
│   ├── guardrails/                    #   Base rule engine (injection, PII, toxicity)
│   └── gateway/policy.py             #   Shared policy stack: rate limit → RBAC → budget → audit
│
├── data_ingestion/                    # Shared text processing (no cloud dependency)
│   ├── chunking/                      #   Fixed-token and sentence chunkers
│   ├── etl/cleaner.py                 #   PII detection + document normalisation
│   └── sources/base.py               #   BaseSourceConnector, RawDocument
│
├── providers/                         # One sub-package per deployment target
│   ├── open_source/                   #   OSS: LiteLLM, Qdrant, LangGraph, MLflow
│   ├── azure/                         #   Azure AI Foundry stack
│   ├── aws/                           #   AWS AgentCore stack
│   └── gcp/                           #   GCP Vertex AI stack
│   (each provider contains: data_ingestion/, storage/, model_development/,
│    serving/gateway+agents, observability/, governance/, config/settings.py,
│    requirements.txt)
│
├── infra/                             # Infrastructure as Code (Terraform)
│   └── terraform/
│       ├── .gitignore                 #   Excludes .tfstate, .tfvars, .terraform/
│       └── envs/
│           ├── azure/                 #   Azure: Container Apps, AI Search, OpenAI, Redis, ACR
│           │   ├── main.tf
│           │   ├── variables.tf
│           │   ├── outputs.tf
│           │   └── terraform.tfvars.example
│           ├── aws/                   #   AWS: ECS Fargate, OpenSearch, ElastiCache, ECR, ALB
│           │   ├── main.tf  ...
│           └── gcp/                   #   GCP: Cloud Run, Vector Search, Memorystore, AR
│               ├── main.tf  ...
│
├── tests/
│   ├── conftest.py                    # Root conftest: env detection, auto-skip hooks, fixtures
│   ├── unit/                          # Provider-agnostic unit tests (always run in CI)
│   ├── integration/                   # Integration tests (require docker-compose.test.yml)
│   ├── eval_suites/                   # Regression + RAG evaluation suites
│   └── smoke/                         # Post-deployment smoke tests (require GATEWAY_URL)
│       ├── test_health.py             #   /health returns 200
│       ├── test_auth.py               #   RBAC enforcement
│       ├── test_guardrail.py          #   Injection attempts blocked
│       └── test_latency.py            #   p95 latency SLO
│
├── scripts/
│   ├── run_ingestion.py               # --provider flag: open_source | azure | aws | gcp
│   └── run_evals.py                   # --provider + --suite + --mode flags
│
# Environment configuration
├── .env.example                       # Legacy combined example (all providers)
├── .env.development.example           # Dev: localhost endpoints, mock keys, LocalStack
├── .env.staging.example               # Staging: cloud staging endpoints, CI secret refs
├── .env.production.example            # Production: names only — no values (use secrets manager)
│
# Open-source-specific (root-level for backward compatibility)
├── storage/                           # Qdrant, Feast, S3, prompt registry
├── model_development/                 # MLflow, W&B, HuggingFace PEFT
├── observability/                     # OTel, Prometheus, drift detector
├── config/                            # Settings, LiteLLM config, Grafana dashboards
├── helm/                              # Kubernetes Helm chart
├── docker-compose.yml                 # Full OSS development stack
├── docker-compose.test.yml            # Lightweight CI stack (Qdrant, Redis, LocalStack, WireMock)
└── requirements.txt                   # Shared base deps (pydantic, fastapi, otel, httpx, etc.)
```

---

## Architectural Rules

1. **`core/` imports only stdlib and pydantic** — never a cloud SDK.
2. **`governance/` imports only stdlib, pydantic, and `core/`** — never a cloud SDK.
3. **Providers import from `core/` and root `governance/` only** — never from each other.
4. **Every provider implements the same ABCs** — swap provider in config without changing application code.
5. **Shared `requirements.txt` covers only base deps** — each provider has its own `requirements.txt`.

---

## Framework Maturity Modes

Set `APP_COMPLEXITY` to choose how strict the framework should be:

| Mode | Purpose | Stub policy |
|---|---|---|
| `reference` | Local framework development, demos, docs, deterministic tests | Explicit stubs may pass and emit reports |
| `starter-production` | One provider, real data, auth, secrets, evals, observability | Stubs fail gates unless replaced |
| `regulated-production` | Stronger audit, PII controls, approvals, private networking | Stubs fail gates unless replaced |
| `multi-cloud-enterprise` | Provider parity, cross-cloud governance, multi-provider evals | Stubs fail gates unless replaced |

Allowed stubs must be documented as extension points, write an explicit
`status=stubbed` report, pass only in `reference` mode, and fail in production
modes until replaced by a real implementation. This keeps the framework
adaptable without letting CI/CD or eval gates claim false production coverage.

---

## Environment Strategy

The framework enforces a three-tier environment model. Cloud infrastructure is **only
provisioned or deployed in staging and production** — local development uses Docker
Compose mocks. Production deploys require an explicit human-approved promotion step.

```
development  ──►  staging (auto on main push)  ──►  production (manual approval)
     │                      │                               │
Docker Compose          Cloud infra                   Cloud infra
LocalStack (AWS mock)   (non-prod tier)               (prod tier, HA)
WireMock (LLM stub)     Separate credentials          Separate credentials
Unit + integration      Regression + safety evals     Post-deploy smoke tests
tests (no cloud)        Post-deploy smoke tests       Required reviewers gate
```

### Credential isolation

Each GitHub Environment (`development`, `staging`, `production`) holds a **separate**
set of secrets pointing to different service principals / IAM roles / WIF bindings:

| GitHub Environment | Azure secret | AWS secret | GCP secret |
|---|---|---|---|
| `staging` | `AZURE_CLIENT_ID` → staging SP | `AWS_DEPLOY_ROLE_ARN` → staging role | `GCP_WIF_PROVIDER` + `GCP_DEPLOY_SA` |
| `production` | `AZURE_CLIENT_ID_PROD` → prod SP | `AWS_DEPLOY_ROLE_ARN_PROD` → prod role | `GCP_WIF_PROVIDER_PROD` + `GCP_DEPLOY_SA_PROD` |

The staging service principal has no write access to production resources.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker Desktop (for local services)
- Terraform >= 1.7 (for cloud provisioning)
- Git

### 1. Clone and create a virtual environment

```bash
git clone <repo-url> && cd llmops_project
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
```

### 2. Install dependencies for your chosen provider

```bash
# Open source (default)
pip install -r requirements.txt -r providers/open_source/requirements.txt

# Azure AI Foundry
pip install -r requirements.txt -r providers/azure/requirements.txt

# AWS AgentCore
pip install -r requirements.txt -r providers/aws/requirements.txt

# GCP Vertex AI
pip install -r requirements.txt -r providers/gcp/requirements.txt
```

### 3. Configure environment variables

```bash
# Development (local services via docker-compose.test.yml)
cp .env.development.example .env.development
# Edit .env.development — fill in any personal API keys you want to use locally
export APP_ENV=development
export APP_COMPLEXITY=reference

# Staging / production — see provider-specific sections below
```

The application loads `.env` first, then `.env.<APP_ENV>` as an override layer.
Values in `.env.development` override any matching key in the base `.env`.

### 4. Start local services for development / CI

```bash
# Lightweight test stack (Qdrant, Redis, LocalStack, WireMock)
docker compose -f docker-compose.test.yml up -d

# Full OSS development stack (adds MLflow, Jaeger, Prometheus, Grafana, Kafka)
docker compose up -d
```

### 5. Run unit tests (no cloud required)

```bash
pytest                          # runs unit tests only (default addopts filter)
pytest -m integration           # needs docker-compose.test.yml running
pytest -m smoke                 # needs GATEWAY_URL pointing to a deployed gateway
```

### 6. Run the ingestion pipeline

```bash
python scripts/run_ingestion.py --provider open_source   # or azure / aws / gcp
```

### 7. Start the gateway

```bash
# Direct (development)
uvicorn serving.gateway.app:app --port 4000                          # open_source
uvicorn providers.azure.serving.gateway.app:app --port 4001          # azure
uvicorn providers.aws.serving.gateway.app:app --port 4002            # aws
uvicorn providers.gcp.serving.gateway.app:app --port 4003            # gcp

# Docker (matches what CI/CD builds and deploys)
docker build --build-arg PROVIDER=azure -t llmops-gateway:azure .
docker build --build-arg PROVIDER=aws   -t llmops-gateway:aws .
docker build --build-arg PROVIDER=gcp   -t llmops-gateway:gcp .
docker build                             -t llmops-gateway:oss .    # defaults to open_source
docker run --env-file .env.development -p 4001:4001 llmops-gateway:azure
```

### 8. Run evaluations

```bash
python scripts/run_evals.py --suite safety     --provider open_source
python scripts/run_evals.py --suite regression --provider azure
python scripts/run_evals.py --suite agent      --provider aws --mode multi
```

In `reference` mode, regression evals use deterministic sample data unless
`LLMOPS_RUN_LIVE_EVALS=1` is set. RAG retrieval and RAG end-to-end evals are
explicit extension-point stubs in `reference` mode and fail in production modes
until a real vector-store-backed dataset and thresholds are configured.

---

## RAG Flexibility

RAG is configurable because applications differ in corpus size, security posture,
latency targets, and reasoning needs.

| Variable | Options | Purpose |
|---|---|---|
| `RAG_RETRIEVAL_MODE` | `vector`, `hybrid`, `graph_augmented`, `hybrid_graph` | Chooses semantic, keyword+semantic, graph-expanded, or combined retrieval |
| `RAG_SECURITY_MODE` | `none`, `metadata_filtering`, `acl_filtering`, `policy_enforced_acl` | Chooses public corpus, coarse metadata filters, user/group ACLs, or strict policy-backed ACLs |
| `GRAPH_ENABLED` | `true`, `false` | Enables graph-dependent retrieval modes |
| `RERANKER_ENABLED` | `true`, `false` | Enables a provider/custom reranker when available |

Provider guidance:

| Provider | Vector | Hybrid | Optional graph | ACL filtering |
|---|---|---|---|---|
| Open source | Qdrant | Adapter surface available; use Qdrant hybrid config or OpenSearch/Elasticsearch | Neo4j, ArangoDB, Memgraph via `search_graph_augmented` | App-layer ACL fields translated to vector/keyword filters |
| Azure | Azure AI Search vector | `search_hybrid` uses Azure AI Search keyword + vector | Cosmos DB Gremlin, Neo4j, Azure SQL graph patterns via `search_graph_augmented` | Entra/user/group fields translated to OData filters during Azure AI Search retrieval |
| AWS | OpenSearch k-NN | `search_hybrid` combines BM25 and k-NN in OpenSearch | Amazon Neptune or graph adapter via `search_graph_augmented` | Cognito/IAM/app ACL fields translated to OpenSearch bool/terms filters |
| GCP | Vertex AI Vector Search | Adapter surface available; pair Vertex Vector Search with keyword index or BigQuery search pattern | Neo4j, Spanner Graph, or graph adapter via `search_graph_augmented` | IAP/IAM/app ACL fields translated to Vertex restricts/metadata filters |

Security trade-off: post-retrieval filtering is acceptable only for low-risk
reference or internal corpora. For applications with document-level permissions,
ACL constraints must be applied before or during retrieval, and eval/smoke tests
must prove unauthorized chunks cannot be returned. Use `policy_enforced_acl` for
regulated environments where retrieval decisions need auditability.

Provider-specific finalization templates live in:

- [`docs/use_case_templates/open_source_use_case_template.md`](docs/use_case_templates/open_source_use_case_template.md)
- [`docs/use_case_templates/azure_use_case_template.md`](docs/use_case_templates/azure_use_case_template.md)
- [`docs/use_case_templates/aws_use_case_template.md`](docs/use_case_templates/aws_use_case_template.md)
- [`docs/use_case_templates/gcp_use_case_template.md`](docs/use_case_templates/gcp_use_case_template.md)

Use the relevant template once a specific use case is known. It captures the
business goal, data sources, RAG mode, ACL model, eval thresholds, platform
services, and production gates needed to complete the implementation safely.

Implementation surface:

- `AbstractRAGRetriever` defines the provider-neutral retrieval contract.
- `GenericRAGRetriever` dispatches to `search`, `search_hybrid`, or
  `search_graph_augmented` when a backend exposes those methods.
- `build_provider_rag_retriever(provider)` resolves the current provider's
  retriever factory without importing cloud SDKs until needed.
- ACL leakage tests should be added for every project corpus before production.

---

## Infrastructure Provisioning (Terraform)

Each cloud provider has a self-contained Terraform environment under
`infra/terraform/envs/<provider>/`. All three use remote state backends.

### What each Terraform stack provisions

| Resource | Azure | AWS | GCP |
|---|---|---|---|
| Compute | Container Apps | ECS Fargate + ALB | Cloud Run |
| LLM | Azure OpenAI (gpt-4o + embedding) | Bedrock IAM policy | Vertex AI IAM |
| Vector store | AI Search (HNSW) | OpenSearch (k-NN) | Vertex Vector Search index + endpoint |
| Cache | Azure Cache for Redis | ElastiCache Redis | Memorystore Redis |
| Data lake | ADLS Gen2 | S3 + versioning | GCS + versioning |
| Registry | ACR | ECR + lifecycle policy | Artifact Registry |
| Identity | Managed Identity + RBAC | IAM task roles | Service Account + IAM |
| Secrets | Key Vault | Secrets Manager | Secret Manager |
| Networking | Container Apps env | VPC + NAT + SGs | VPC + Serverless connector |
| State backend | Azure Blob (`azurerm`) | S3 + DynamoDB locking | GCS |

### First-time bootstrap

```bash
# Step 1: create the remote state storage (one-time, outside Terraform)
# Azure:
az storage account create -n tfstatesa -g tfstate-rg -l eastus2 --sku Standard_LRS
az storage container create -n tfstate --account-name tfstatesa

# AWS:
aws s3 mb s3://my-tfstate-bucket --region us-east-1
aws dynamodb create-table --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# GCP:
gsutil mb -l us-central1 gs://my-tfstate-bucket

# Step 2: copy and fill in tfvars
cd infra/terraform/envs/azure
cp terraform.tfvars.example terraform.tfvars    # fill in values

# Step 3: init + apply (gateway_image=placeholder on the first run)
terraform init -backend-config="storage_account_name=tfstatesa" \
               -backend-config="container_name=tfstate" \
               -backend-config="resource_group_name=tfstate-rg" \
               -backend-config="key=llmops-staging.tfstate"
terraform apply -var="gateway_image=placeholder"

# Step 4: once the registry exists, build and push your image, then re-apply
# The CI/CD workflows handle steps 3-4 automatically on subsequent runs.
```

### Outputs used by CI/CD

After `terraform apply`, key outputs are captured and passed between pipeline stages:

```bash
terraform output gateway_url          # URL of the deployed gateway
terraform output acr_login_server     # Azure: registry for image push
terraform output ecr_repository_url   # AWS: ECR URL
terraform output artifact_registry_url # GCP: AR URL
```

---

## CI/CD Pipeline Architecture

Workflow files live in [`.github/workflows/`](.github/workflows/) — the only location
GitHub Actions reads. Reference copies are kept in `governance/cicd/` for documentation.

### Staging deployment (auto on `main` push)

Three independent workflows run in parallel — one per provider:

```
Push to main
    │
    ▼
infra (terraform apply → staging)
    │
    ▼
build (docker build → push to ACR/ECR/AR)
    │
    ▼
eval-gate (regression ≥ 90% + safety ≥ 95%)
    │
    ▼
deploy (Container Apps / ECS / Cloud Run canary)
    │
    ▼
post-deploy smoke tests (health + auth + guardrail + latency)
```

### Production promotion (manual, gated)

Triggered by pushing a semver tag (`v1.2.3`) **or** via `workflow_dispatch`. Requires
explicit approval from GitHub Environment protection (`production` → Required reviewers).

```
Tag push / workflow_dispatch
    │
    ▼
pre-promotion eval gate (regression ≥ 92% + safety ≥ 98% across all providers)
    │
    ▼
staging smoke tests (all 3 providers)
    │
    ▼
[ Required reviewers approval ]
    │
    ├── promote-azure (terraform apply production + smoke tests)
    ├── promote-aws   (terraform apply production + smoke tests)
    └── promote-gcp   (terraform apply production + canary → 100% + smoke tests)
    │
    ▼
GitHub Release created
```

**Key rule:** `deploy_*.yml` workflows hard-block environment=`production` at the `if:` condition level.
Production access is only available through `promote_to_production.yml` using
`*_PROD`-suffixed secrets tied to the `production` GitHub Environment.

---

## Testing Pyramid

| Tier | Command | When | Needs |
|---|---|---|---|
| **Unit** | `pytest` | Every commit, local and CI | Nothing — no services required |
| **Integration** | `pytest -m integration` | PR, CI | `docker-compose.test.yml` running |
| **Eval suite** | `python scripts/run_evals.py` | CI eval-gate stage | LLM API credentials |
| **Smoke** | `pytest -m smoke` | Post-deploy in CI; manual against live envs | `GATEWAY_URL` env var |
| **Cloud** | `pytest -m requires_cloud` | Manual or nightly | Real cloud credentials (`LLMOPS_RUN_CLOUD_TESTS=1`) |

### Running integration tests locally

```bash
# Start local services
docker compose -f docker-compose.test.yml up -d

# Run integration tests
APP_ENV=development \
LLMOPS_LOCALSTACK_URL=http://localhost:4566 \
pytest -m integration -v

# Tear down
docker compose -f docker-compose.test.yml down -v
```

### Running smoke tests against a deployed gateway

```bash
# Point at staging
GATEWAY_URL=https://llmops-staging-gateway.example.com \
APP_ENV=staging \
X_USER_ID=smoke-user \
X_USER_ROLE=developer \
pytest tests/smoke/ -m smoke -v

# Tune latency threshold (default 5.0 s)
SMOKE_P95_THRESHOLD_S=3.0 pytest tests/smoke/test_latency.py -m smoke -v
```

### Pytest markers

| Marker | Default | Description |
|---|---|---|
| `unit` | ✅ Runs | No external dependencies |
| `integration` | ❌ Skipped | Needs docker-compose.test.yml |
| `eval` | ❌ Skipped | Needs LLM API access |
| `slow` | ❌ Skipped | Fine-tuning, large datasets |
| `requires_cloud` | ❌ Skipped | Real cloud credentials — set `LLMOPS_RUN_CLOUD_TESTS=1` |
| `requires_localstack` | ❌ Skipped* | LocalStack — set `LLMOPS_LOCALSTACK_URL` |
| `smoke` | ❌ Skipped* | Live gateway — set `GATEWAY_URL` |

\* Auto-skipped by `tests/conftest.py` hooks when the prerequisite service is not detected.

---

## Shared Components Reference

| Module | What it does | File |
|---|---|---|
| `SemanticCache` | Two-level LLM cache: exact SHA-256 match + cosine similarity fallback | `serving/cache/semantic_cache.py` |
| `GuardrailRunner` | Input/output scan: prompt injection, PII (SSN, CC, email), toxicity keywords | `serving/guardrails/guardrail_runner.py` |
| `PolicyContext` | FastAPI dependency: rate limit → RBAC → guardrails → budget → audit | `serving/gateway/policy.py` |
| `RBACEnforcer` | Role-based access control with model allowlists | `governance/access_control/rbac.py` |
| `AuditLogger` | SHA-256 tamper-evident audit record for every LLM interaction | `governance/audit/audit_logger.py` |
| `CostManager` | Per-team daily/monthly/per-request budget enforcement | `governance/cost/cost_manager.py` |
| `DocumentCleaner` | PII redaction + text normalisation | `data_ingestion/etl/cleaner.py` |
| Token/sentence chunker | Fixed-token and sentence-boundary chunking | `data_ingestion/chunking/chunker.py` |
| `EvalResult` | Standardised eval output (faithfulness, relevancy, latency) | `core/schemas/evaluation.py` |

---

---

# Adapting the Framework for a Real Project

The sections below describe every step required to take this framework from
reference architecture to a **production LLMOps system** on your chosen platform.
Follow the steps in order: infrastructure → environment → data → model → serving → observability → governance.

---

## Option A — Open Source

Use this stack when you need full data sovereignty, no vendor lock-in, the ability
to run entirely on-premises or in any cloud, or when your budget requires it.

### Prerequisites

| Service | Minimum | Production recommendation |
|---|---|---|
| Qdrant | Docker single-node | Qdrant Cloud or Kubernetes cluster |
| MLflow | SQLite + local filesystem | PostgreSQL backend + S3 artifact store |
| Redis | Docker single-node | Redis Sentinel or Redis Cluster |
| Kafka | Docker single-broker | Confluent Cloud or MSK |
| LiteLLM | Docker | Kubernetes with HPA |

### Step 1 — Environment variables

```bash
cp .env.development.example .env.development
export APP_ENV=development

# Key variables to set:
OPENAI_API_KEY=sk-...           # or ANTHROPIC_API_KEY for Claude
LITELLM_MASTER_KEY=your-key
QDRANT_URL=http://localhost:6333
MLFLOW_TRACKING_URI=http://localhost:5000
REDIS_URL=redis://localhost:6379
```

For staging, copy `.env.staging.example` → `.env.staging` and point at your
cloud-hosted services. For production, values are injected by Helm/Kubernetes
from a secrets manager — see `.env.production.example`.

### Step 2 — Replace the stub source connectors

`data_ingestion/sources/file_connector.py` reads from a local directory or S3.
For a real project, implement `BaseSourceConnector.fetch()` for your actual data sources:

```python
# data_ingestion/sources/my_connector.py
from data_ingestion.sources.base import BaseSourceConnector, RawDocument

class ConfluenceConnector(BaseSourceConnector):
    def fetch(self) -> list[RawDocument]:
        # Call Confluence REST API, return RawDocument list
        ...
```

### Step 3 — Configure the LiteLLM routing table

Edit `config/litellm_config.yaml` to add your models, set fallbacks, and configure
rate limits per team:

```yaml
model_list:
  - model_name: my-gpt-4o
    litellm_params:
      model: openai/gpt-4o
      api_key: os.environ/OPENAI_API_KEY
      rpm: 500

router_settings:
  routing_strategy: latency-based-routing
  fallbacks:
    - my-gpt-4o: [claude-sonnet]
```

### Step 4 — Register budget policies for each team

```python
from governance.cost.cost_manager import CostManager, BudgetPolicy

cm = CostManager()
cm.register_policy(BudgetPolicy(
    team_id="product-team",
    daily_limit_usd=100.0,
    monthly_limit_usd=2000.0,
    per_request_limit_usd=0.50,
))
```

### Step 5 — Wire your user identity into the policy stack

The gateway reads `X-User-Id`, `X-User-Role`, and `X-Team-Id` HTTP headers.
In production, replace the header-based resolver in `serving/gateway/policy.py`
with JWT validation:

```python
from fastapi.security import OAuth2PasswordBearer
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def resolve_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    return User(id=payload["sub"], role=Role(payload["role"]),
                team_id=payload["team_id"])
```

### Step 6 — Tune the semantic cache

```python
_cache = SemanticCache(
    similarity_threshold=0.92,   # raise for precision, lower for recall
    ttl_seconds=3600,
    redis_url=os.getenv("REDIS_URL"),
    embed_model="all-MiniLM-L6-v2",
)
```

### Step 7 — Add your fine-tuned model to the registry

```python
from model_development.model_registry.registry import ModelRegistry
registry = ModelRegistry(tracking_uri="http://localhost:5000")
registry.register_model(run_id="<mlflow-run-id>", model_name="my-finetuned-llm")
registry.transition_stage("my-finetuned-llm", "1", "Production")
```

### Step 8 — Deploy to Kubernetes

```bash
helm install llmops ./helm/llmops \
  --set image.tag=v1.0.0 \
  --set gateway.replicaCount=3 \
  --set qdrant.persistence.size=50Gi
```

---

## Option B — Azure AI Foundry

Use this stack when your organisation is Azure-first, when you need enterprise
security (Entra ID, Azure Policy, Defender for AI), or when data must remain in
a specific Azure region for compliance.

### Prerequisites

- Azure subscription with Contributor access
- Terraform >= 1.7 (or Azure CLI for manual provisioning)
- GitHub repository with `staging` and `production` Environments configured

### Step 1 — Provision infrastructure

```bash
cd infra/terraform/envs/azure
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars: project, env=staging, location, gpt4o_capacity_tpm

terraform init -backend-config="storage_account_name=<tfstate-sa>" \
               -backend-config="container_name=tfstate" \
               -backend-config="resource_group_name=<tfstate-rg>" \
               -backend-config="key=llmops-staging.tfstate"
terraform apply -var="gateway_image=placeholder"
# Note the outputs: acr_login_server, openai_endpoint, ai_search_endpoint
```

Terraform provisions: Resource Group, Key Vault, ACR, Azure OpenAI (gpt-4o + embedding),
AI Search (HNSW), Redis, ADLS Gen2, Log Analytics, App Insights, Azure ML workspace,
Container Apps environment + gateway app, Managed Identity with RBAC role assignments.

### Step 2 — Environment variables

After `terraform apply`, populate `.env.staging` with the Terraform outputs:

```bash
AZURE_OPENAI_ENDPOINT=$(terraform output -raw openai_endpoint)
AZURE_AI_SEARCH_ENDPOINT=$(terraform output -raw ai_search_endpoint)
AZURE_STORAGE_ACCOUNT_NAME=$(terraform output -raw storage_account_name)
AZURE_APPINSIGHTS_CONNECTION_STRING=$(terraform output -raw app_insights_connection_string)
# Store the above in GitHub Environment secrets for the staging environment
```

In production, **all values are injected from Key Vault references** — see
`.env.production.example`. The `AZURE_CLIENT_SECRET` must be absent in production;
the gateway authenticates via Managed Identity automatically.

### Step 3 — Replace the data source connector

`providers/azure/data_ingestion/adf_connector.py` reads from ADLS Gen2.
For SharePoint or Teams data, extend it:

```python
class SharePointConnector(BaseSourceConnector):
    def fetch(self) -> list[RawDocument]:
        # Use Microsoft Graph API (msgraph-sdk-python)
        ...
```

### Step 4 — Enable Managed Identity (production)

No code changes required — `DefaultAzureCredential` picks up Managed Identity
automatically when `AZURE_CLIENT_ID/SECRET` are absent. The Terraform stack already
assigns the Container App's Managed Identity the required roles:
`Cognitive Services OpenAI User`, `Search Index Data Contributor`, `Storage Blob Data Contributor`.

If `AZURE_CLIENT_SECRET` is set in production, the application will emit a
`warnings.warn` at startup to alert you to the misconfiguration.

### Step 5 — Activate Azure Content Safety

```python
# serving/gateway/policy.py — swap the guardrails singleton
from providers.azure.governance.content_safety import AzureContentSafetyGuardrails
_guardrails = AzureContentSafetyGuardrails(severity_threshold=4)
```

### Step 6 — Set up multi-agent with Foundry

`providers/azure/serving/agents/foundry_agent.py` handles both single and multi-agent
runs. To add Bing grounding:

```python
tools=[
    {"type": "bing_grounding",
     "bing_grounding": {"connection_id": "<bing-connection-id>"}},
    {"type": "code_interpreter"},
]
```

### Step 7 — Deploy via CI/CD

Push to `main` → `deploy_azure.yml` auto-deploys to staging.
When ready for production, push a semver tag or trigger `promote_to_production.yml`
manually — requires required-reviewers approval on the `production` GitHub Environment.

```bash
git tag v1.2.0 && git push origin v1.2.0   # triggers promote_to_production.yml
```

---

## Option C — AWS AgentCore

Use this stack when your organisation is AWS-first, when your data already lives
in S3, when you need SageMaker for fine-tuning, or when compliance requires AWS
GovCloud or AWS PrivateLink.

### Prerequisites

- AWS account with IAM permissions for: Bedrock, ECS, OpenSearch, S3, ECR, ElastiCache
- Bedrock model access granted for Claude 3.5 Sonnet + Titan Embeddings V2
- GitHub OIDC provider configured in IAM → trust relationship for `AWS_DEPLOY_ROLE_ARN`

### Step 1 — Provision infrastructure

```bash
cd infra/terraform/envs/aws
cp terraform.tfvars.example terraform.tfvars

terraform init -backend-config="bucket=<tfstate-bucket>" \
               -backend-config="key=llmops/staging/terraform.tfstate" \
               -backend-config="region=us-east-1" \
               -backend-config="dynamodb_table=terraform-locks"
terraform apply -var="gateway_image=placeholder"
# Note outputs: ecr_repository_url, alb_dns_name, opensearch_endpoint
```

Terraform provisions: VPC + NAT Gateway, ECR, OpenSearch domain (k-NN enabled),
ElastiCache Redis, S3 bucket (versioned + encrypted), IAM task role (Bedrock + S3 + CW
permissions), ECS Cluster + Fargate task + ALB, CloudWatch log group.

### Step 2 — Environment variables

```bash
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
OPENSEARCH_ENDPOINT=$(terraform output -raw opensearch_endpoint)
AWS_REDIS_URL=$(terraform output -raw redis_endpoint)
S3_BUCKET=$(terraform output -raw s3_bucket_name)
```

In production, all values come from ECS task definition environment variables
populated from Secrets Manager. Static access keys (`AWS_ACCESS_KEY_ID`) must be
absent in production — the ECS task IAM role is used instead. The settings class
will warn if static credentials are detected at startup.

### Step 3 — Grant Bedrock model access

In the AWS Console → Amazon Bedrock → Model access, request access for:
- Anthropic Claude 3.5 Sonnet
- Amazon Titan Embeddings V2

Access is per-region. Re-run for each region you deploy to.

### Step 4 — Configure Bedrock Guardrails

Create a guardrail in the Bedrock console → set `BEDROCK_GUARDRAIL_ID`.
The framework calls `ApplyGuardrail` for every request automatically.

### Step 5 — Replace the data source connector

`providers/aws/data_ingestion/glue_connector.py` reads from S3. For Kinesis or RDS:

```python
class KinesisConnector(BaseSourceConnector):
    def fetch(self) -> list[RawDocument]:
        kinesis = boto3.client("kinesis", region_name=get_aws_settings().aws_region)
        ...
```

### Step 6 — Deploy via CI/CD

Push to `main` → `deploy_aws.yml` deploys to staging (ECS rolling update).
For production: push a semver tag or trigger `promote_to_production.yml`.

---

## Option D — GCP Vertex AI

Use this stack when your organisation is GCP-first, when you use BigQuery for
analytics, when Gemini models are preferred, or when you need tight Google
Workspace integration.

### Prerequisites

- GCP project with billing enabled
- GitHub OIDC Workload Identity Federation configured for the deploy service account
- `gcloud` CLI installed locally for bootstrap commands

### Step 1 — Provision infrastructure

```bash
cd infra/terraform/envs/gcp
cp terraform.tfvars.example terraform.tfvars
# Edit: gcp_project_id, env, gcp_region

terraform init -backend-config="bucket=<tfstate-bucket>" \
               -backend-config="prefix=llmops/staging"
terraform apply -var="gcp_project_id=<project>" -var="gateway_image=placeholder"
# Note: Vertex AI Vector Search index creation takes 20-60 minutes on first apply.
```

Terraform provisions: API enablement, VPC + Serverless connector, Service Account
+ IAM bindings, Artifact Registry, GCS bucket (versioned), Memorystore Redis,
Vertex AI Vector Search index + endpoint + deployed index, Cloud Run service,
Secret Manager secret for Perspective API key.

### Step 2 — Environment variables

```bash
GCP_PROJECT_ID=<project>
GCS_BUCKET=$(terraform output -raw gcs_bucket_name)
VECTOR_SEARCH_INDEX_ENDPOINT=$(terraform output -raw vector_index_endpoint_id)
VECTOR_SEARCH_DEPLOYED_INDEX_ID=$(terraform output -raw vector_deployed_index_id)
REDIS_HOST=$(terraform output -raw redis_host)
```

In production, values come from Cloud Run environment variables and Secret Manager.
The `GOOGLE_APPLICATION_CREDENTIALS` key file must be absent in production
(Cloud Run uses the service account binding). The settings class will warn if
a key file path is detected at startup.

### Step 3 — Replace the data source connector

`providers/gcp/data_ingestion/dataflow_connector.py` reads from GCS.
For BigQuery:

```python
class BigQueryConnector(BaseSourceConnector):
    def fetch(self) -> list[RawDocument]:
        from google.cloud import bigquery
        client = bigquery.Client(project=get_gcp_settings().gcp_project_id)
        rows = client.query("SELECT id, content FROM `dataset.documents`").result()
        return [RawDocument(id=str(r.id), source="bigquery", content=r.content)
                for r in rows]
```

### Step 4 — Adjust Gemini safety settings

```python
from vertexai.generative_models import HarmCategory, HarmBlockThreshold, SafetySetting

safety_settings = [
    SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                  threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
]
```

### Step 5 — Deploy via CI/CD

Push to `main` → `deploy_gcp.yml` deploys to staging with a canary (10% traffic
→ smoke tests → 100%). For production: push a semver tag or trigger
`promote_to_production.yml` — includes the same canary pattern at production scale.

---

## Cross-Provider Customisation Guide

### Finalise for a specific use case

1. Select the platform template under `docs/use_case_templates/`.
2. Fill in business goals, data sources, security requirements, RAG mode, evals, and SLOs.
3. Set `APP_PROVIDER`, `APP_ENV`, `APP_COMPLEXITY`, `RAG_RETRIEVAL_MODE`, and `RAG_SECURITY_MODE`.
4. Implement provider-specific adapters for any selected optional capabilities, such as hybrid search, graph augmentation, reranking, or policy-enforced ACL.
5. Replace reference stubs with real eval, benchmark, latency, model-promotion, and smoke gates.
6. Run staging CI/CD and promote only after production-mode gates produce no `status=stubbed` reports.

### Customise guardrails

```python
# serving/guardrails/guardrail_runner.py — extend PII patterns
_PII_PATTERNS = {
    "ssn":         re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){15,16}\b"),
    "email":       re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b"),
    "uk_nino":     re.compile(r"\b[A-Z]{2}\d{6}[A-D]\b"),
}
_TOXIC_KEYWORDS = frozenset(load_blocklist("data/blocklist.txt"))
```

Cloud guardrail extensions are subclasses — they run base rules first,
then call the managed API (Azure Content Safety / Bedrock Guardrails / Perspective API).

### Customise cost budgets

```python
from governance.cost.cost_manager import CostManager, BudgetPolicy
cm = CostManager(ledger_path="data/cost_ledger.jsonl")
for team_id, limits in TEAM_CONFIG.items():
    cm.register_policy(BudgetPolicy(team_id=team_id, **limits))
```

### Customise RBAC

```python
# governance/access_control/rbac.py
PERMISSIONS["agent:run"]       = Role.DEVELOPER
PERMISSIONS["agent:run_multi"] = Role.ML_ENGINEER
PERMISSIONS["data:export"]     = Role.ADMIN
```

### Add a new data source connector

1. Create `data_ingestion/sources/my_source.py` implementing `BaseSourceConnector`.
2. Register it in `scripts/run_ingestion.py` under your `--provider` branch.
3. The cleaning and chunking pipeline is unchanged — pass `RawDocument` objects.

### Add a new agent tool

- OSS (LangGraph): add a `@tool`-decorated function to `serving/agents/langgraph_agent.py`
- Azure Foundry: add a `ToolDefinition` to the agent spec in `foundry_agent.py`
- AWS Bedrock: add an action group Lambda in `agentcore.py`
- GCP Vertex: add a `FunctionDeclaration` to `_TOOLS` in `agent_engine.py`

### Replace embeddings

```python
# SemanticCache
_cache = SemanticCache(embed_model="BAAI/bge-large-en-v1.5", ...)

# QdrantVectorStore
store = QdrantVectorStore(embedding_model="BAAI/bge-large-en-v1.5", vector_size=1024)
```

---

## Production Readiness Checklist

### Infrastructure

- [ ] Terraform state stored in remote backend with state locking (not local)
- [ ] Separate Terraform workspaces / state files for staging vs production
- [ ] No `terraform.tfvars` committed to source control (covered by `infra/terraform/.gitignore`)
- [ ] Production service principal / IAM role has least-privilege permissions only
- [ ] `*_PROD` secrets stored in GitHub `production` Environment (not in `staging`)

### Security

- [ ] Replace placeholder toxic keyword list with a real blocklist
- [ ] Replace header-based user identity with JWT / OAuth2 / OIDC validation
- [ ] Long-lived credentials absent from production config (Managed Identity / IAM role / WIF)
- [ ] All API keys rotated and stored in secrets manager (Key Vault / Secrets Manager / Secret Manager)
- [ ] TLS enforced on all service endpoints
- [ ] `AuditConfig(store_full_content=False, redact_pii=True)` set for HIPAA/GDPR environments

### Application

- [ ] Budget policies registered for every team (`CostManager.register_policy`)
- [ ] `REDIS_URL` set to managed Redis (not in-process dict fallback)
- [ ] `OTEL_EXPORTER_OTLP_ENDPOINT` configured (or cloud-native exporter enabled)
- [ ] `APP_ENV=production` set — triggers env-specific `.env.production` overrides and credential warnings
- [ ] `APP_COMPLEXITY` set to `starter-production`, `regulated-production`, or `multi-cloud-enterprise`
- [ ] All explicit reference-mode stubs replaced or accepted as non-production documentation examples

### CI/CD gates

- [ ] GitHub `production` Environment has required reviewers configured
- [ ] `deploy_*.yml` workflow options list does not include `production` (verified)
- [ ] All unit tests pass: `pytest tests/unit/`
- [ ] Safety eval ≥ 98%: `python scripts/run_evals.py --suite safety --min-pass-rate 0.98`
- [ ] Smoke tests pass against staging before promoting: `pytest tests/smoke/ -m smoke`
- [ ] Post-promote smoke tests pass against production

### Full pipeline gate sequence

```
Unit tests → Integration tests → Regression evals (≥ 90%) →
Safety evals (≥ 95% staging / ≥ 98% production) →
Container scan (Trivy, CRITICAL/HIGH = fail) →
Staging deploy → Post-deploy smoke tests →
[ Required reviewers approval ] →
Production promote → Post-promote smoke tests
```

---

## Environment Variables Reference

| Variable | Provider | Description |
|---|---|---|
| `APP_ENV` | All | `development` / `staging` / `production` — controls `.env.<APP_ENV>` loading |
| `APP_COMPLEXITY` | All | `reference` / `starter-production` / `regulated-production` / `multi-cloud-enterprise` — controls stub strictness |
| `RAG_RETRIEVAL_MODE` | RAG | `vector` / `hybrid` / `graph_augmented` / `hybrid_graph` |
| `RAG_SECURITY_MODE` | RAG | `none` / `metadata_filtering` / `acl_filtering` / `policy_enforced_acl` |
| `GRAPH_ENABLED` | RAG | Must be `true` for graph-based retrieval modes |
| `RERANKER_ENABLED` | RAG | Enables provider/custom reranking when implemented |
| `OPENAI_API_KEY` | OSS | OpenAI models via LiteLLM |
| `ANTHROPIC_API_KEY` | OSS | Anthropic Claude via LiteLLM |
| `REDIS_URL` | All | Semantic cache backend |
| `LLMOPS_RUN_CLOUD_TESTS` | Testing | Set to `1` to enable `requires_cloud` pytest marker |
| `LLMOPS_LOCALSTACK_URL` | Testing | LocalStack URL — enables `requires_localstack` marker |
| `GATEWAY_URL` | Testing | Live gateway URL — enables `smoke` pytest marker |
| `AZURE_OPENAI_ENDPOINT` | Azure | Azure OpenAI resource URL |
| `AZURE_CLIENT_SECRET` | Azure | Dev/staging only — absent in production (Managed Identity) |
| `AZURE_AI_PROJECT_CONNECTION_STRING` | Azure | AI Foundry project |
| `AZURE_APPINSIGHTS_CONNECTION_STRING` | Azure | Observability export |
| `AZURE_CONTENT_SAFETY_ENDPOINT` | Azure | Guardrails API |
| `AWS_REGION` | AWS | Bedrock + SageMaker region |
| `BEDROCK_MODEL_ID` | AWS | Default Bedrock model |
| `BEDROCK_GUARDRAIL_ID` | AWS | Guardrail resource ID |
| `OPENSEARCH_ENDPOINT` | AWS | Vector store |
| `AWS_ACCESS_KEY_ID` | AWS | Dev/staging only — absent in production (IAM role) |
| `GCP_PROJECT_ID` | GCP | Project for all GCP calls |
| `VERTEX_INDEX_ENDPOINT_ID` | GCP | Vector search endpoint |
| `PERSPECTIVE_API_KEY` | GCP | Toxicity scoring |
| `GOOGLE_APPLICATION_CREDENTIALS` | GCP | Dev only — absent in production (WIF service account) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OSS | Jaeger / Langfuse endpoint |

See `.env.development.example`, `.env.staging.example`, and `.env.production.example`
for the full list with comments for each environment tier.

---

## Key Technologies by Provider

| Layer | Open Source | Azure | AWS | GCP |
|---|---|---|---|---|
| **LLM** | LiteLLM (OpenAI/Anthropic/local) | Azure OpenAI | Amazon Bedrock | Vertex Gemini |
| **Vector store** | Qdrant | Azure AI Search | Amazon OpenSearch | Vertex Vector Search |
| **Data lake** | S3 / MinIO | Azure Blob / ADLS Gen2 | Amazon S3 | Google Cloud Storage |
| **Experiments** | MLflow + W&B | Azure ML Experiments | SageMaker Experiments | Vertex AI Experiments |
| **Model registry** | MLflow Registry | Azure ML Registry | SageMaker Registry | Vertex AI Registry |
| **Fine-tuning** | HuggingFace PEFT (LoRA) | Azure AI Foundry Fine-tuning | SageMaker Training | Vertex AI Tuning |
| **Single agent** | LangGraph ReAct | Azure AI Foundry Agents | Bedrock Agents | Vertex Agent Engine |
| **Multi-agent** | CrewAI + LangGraph Supervisor | Foundry multi-agent handoff | AgentCore supervisor | Gemini sequential pipeline |
| **ETL** | Airflow + pandas | Azure Data Factory | AWS Glue | Cloud Composer + Dataflow |
| **Guardrails** | NeMo + rule engine | Azure Content Safety | Bedrock Guardrails | Vertex Safety + Perspective |
| **Tracing** | OpenTelemetry → Jaeger | Azure Monitor + App Insights | AWS X-Ray | Cloud Trace |
| **Metrics** | Prometheus + Grafana | Azure Monitor Metrics | Amazon CloudWatch | Cloud Monitoring |
| **Caching** | Redis (local/managed) | Azure Cache for Redis | ElastiCache | Cloud Memorystore |
| **IaC** | Helm (Kubernetes) | Terraform (azurerm) | Terraform (aws) | Terraform (google) |
| **Deployment** | Docker Compose + Helm/K8s | Azure Container Apps | AWS Fargate | Cloud Run |

---

## Contributing and Feedback

- Issues: open a GitHub issue with the provider label (`provider:azure`, etc.)
- New provider: implement the 8 `core/interfaces/` ABCs + settings + requirements.txt + Terraform env
- New guardrail: subclass `GuardrailRunner` and override `check_input` / `check_output`
- New smoke test: add to `tests/smoke/`, mark with `@pytest.mark.smoke`
