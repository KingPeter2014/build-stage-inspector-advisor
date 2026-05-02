# LLMOps Reference Architecture

## Overview

This project implements a production-grade LLMOps reference architecture in Python,
covering all six operational layers: **data ingestion → storage → model development →
serving → observability → governance**.

---

## Layer 1: Data Ingestion (`data_ingestion/`)

| Component | File | Purpose |
|---|---|---|
| Base connector | `sources/base.py` | Abstract interface for all source connectors |
| SQL connector | `sources/sql_connector.py` | Structured DB ingestion (SQLAlchemy) |
| File connector | `sources/file_connector.py` | PDF, HTML, Markdown, text (local + S3) |
| Stream connector | `sources/stream_connector.py` | Real-time events via Kafka |
| Cleaner | `etl/cleaner.py` | Text normalisation, PII detection + redaction |
| Chunker | `chunking/chunker.py` | Fixed-token and sentence chunking strategies |

**Flow:** Raw sources → ETL/cleaning → PII check → chunking → vector store

---

## Layer 2: Storage (`storage/`)

| Component | File | Purpose |
|---|---|---|
| Vector store | `vector_store/qdrant_store.py` | Qdrant-backed semantic search |
| Feature store | `feature_store/feast_store.py` | Structured features via Feast |
| Data lake | `data_lake/s3_store.py` | Raw/processed/archived data on S3 |
| Prompt registry | `prompt_registry/registry.py` | Versioned prompts (local + Langfuse) |

---

## Layer 3: Model Development (`model_development/`)

| Component | File | Purpose |
|---|---|---|
| Experiment tracker | `experiments/tracker.py` | MLflow / W&B unified interface |
| LoRA fine-tuner | `fine_tuning/lora_trainer.py` | QLoRA fine-tuning with HuggingFace PEFT |
| Eval harness | `evaluation/eval_harness.py` | DeepEval + Ragas evaluation |
| Model registry | `model_registry/registry.py` | Champion/challenger lifecycle via MLflow |

**CI gate:** New model must not regress accuracy by >2% vs. production champion.

---

## Layer 4: Serving (`serving/`)

| Component | File | Purpose |
|---|---|---|
| Gateway | `gateway/app.py` | FastAPI + LiteLLM proxy with cost tracking |
| RAG pipeline | `rag/pipeline.py` | Retrieve → assemble context → generate |
| Agent | `agents/langgraph_agent.py` | ReAct agent with tool use (LangGraph) |
| Guardrails | `guardrails/guardrail_runner.py` | Input/output safety checks |

**Gateway features:** Routing, rate limiting, auth, cost allocation, OpenTelemetry tracing.

**RAG flexibility:** Retrieval can be configured as `vector`, `hybrid`,
`graph_augmented`, or `hybrid_graph`. Security can be configured as `none`,
`metadata_filtering`, `acl_filtering`, or `policy_enforced_acl`. For sensitive
applications, ACL constraints must be applied before or during retrieval, not
only after retrieval.

Use `docs/use_case_templates/<provider>_use_case_template.md` when a specific
use case is known. The completed template should drive provider adapter work,
RAG schema choices, ACL enforcement, eval thresholds, CI/CD gates, and final
production configuration.

---

## Layer 5: Observability (`observability/`)

| Component | File | Purpose |
|---|---|---|
| Tracer | `tracing/tracer.py` | OpenTelemetry setup + OTLP export |
| Prometheus metrics | `metrics/prometheus_metrics.py` | Request counts, tokens, latency, cost, drift |
| Drift detector | `output_eval/drift_detector.py` | Embedding-centroid drift detection |
| Feedback collector | `feedback/collector.py` | User signals → retraining queue |

**Key metrics:** TTFT, P95 latency, token usage, cost/request, faithfulness, drift score.

---

## Layer 6: Governance (`governance/`)

| Component | File | Purpose |
|---|---|---|
| Audit logger | `audit/audit_logger.py` | Tamper-evident audit log (SOC 2/HIPAA) |
| RBAC | `access_control/rbac.py` | Role-based access (Viewer/Dev/ML/Admin) |
| Cost manager | `cost/cost_manager.py` | Token budgets + spend alerts |
| Prompt CI/CD | `cicd/prompt_cicd.yml` | GitHub Actions: lint → eval → promote |
| Model CI/CD | `cicd/model_cicd.yml` | Build → eval gate → canary → promote |
| RAG CI/CD | `cicd/rag_cicd.yml` | Retrieval eval → e2e eval → re-index |

---

## CI/CD Decision Logic

```
Code / prompt / data change
         │
         ▼
    Lint + validate
         │
         ▼
   Regression evals          ← Golden dataset, DeepEval metrics
         │
         ▼
    Safety evals             ← Adversarial inputs, guardrail pass rate ≥ 99%
         │
         ▼
  Container build + scan     ← Trivy (CRITICAL/HIGH findings fail the build)
         │
         ▼
  Integration tests          ← Mocked external dependencies
         │
         ▼
  Latency SLO check          ← P95 < 3.0s
         │
         ▼
  Canary deploy (10%)        ← Monitor error rate for 10 min
         │
         ▼
  Full rollout               ← Requires passing canary window
```

---

## Local Development

```bash
# Start all local services
docker compose up -d

# Run unit tests
pytest tests/unit/ -v

# Seed eval dataset and run regression suite
python scripts/run_evals.py --suite regression --seed

# Run safety evals
python scripts/run_evals.py --suite safety

# Ingest sample documents
mkdir -p data/raw_docs
echo "LLMOps is the practice of operating LLMs." > data/raw_docs/sample.txt
python scripts/run_ingestion.py --source-dir data/raw_docs

# Start the gateway
python serving/gateway/app.py

# Access dashboards
# MLflow:    http://localhost:5000
# Grafana:   http://localhost:3000  (admin/admin)
# Jaeger:    http://localhost:16686
# Qdrant:    http://localhost:6333/dashboard
```

---

## Adding a New Data Source

1. Create `data_ingestion/sources/my_source_connector.py`
2. Subclass `BaseSourceConnector`
3. Implement `validate_connection()` and `fetch()`
4. Add to `scripts/run_ingestion.py`

## Adding a New Prompt

1. Add the prompt to `storage/prompt_registry/registry.py` default seeds
2. Add required variables to `scripts/validate_prompts.py`
3. Push: `python scripts/push_prompts.py --env production`

## Adding a New Eval Metric

1. Add the metric to `model_development/evaluation/eval_harness.py`
2. Add threshold to `scripts/run_evals.py`
3. Update the CI gate in `governance/cicd/prompt_cicd.yml`
