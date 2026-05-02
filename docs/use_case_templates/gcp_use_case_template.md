# GCP Use-Case Finalization Template

Use this when a concrete project chooses GCP Vertex AI / Cloud Run.

## Required Inputs

- Business goal and success metric:
- GCP project, region, and data residency requirement:
- Identity model: IAP / IAM / Workforce Identity / custom JWT:
- Data sources: GCS / BigQuery / Pub/Sub / Google Workspace / custom:
- Corpus sensitivity and compliance requirements:
- RAG retrieval mode: `vector` / `hybrid` / `graph_augmented` / `hybrid_graph`
- RAG security mode: `metadata_filtering` / `acl_filtering` / `policy_enforced_acl`
- Vertex Vector Search index dimensions and restrict schema:
- Keyword backend for hybrid: BigQuery search pattern / OpenSearch / other
- Graph option, if needed: Spanner Graph / Neo4j / custom graph adapter
- Gemini model choice and safety settings:
- Eval datasets and thresholds:
- Latency, cost, and Cloud Monitoring SLOs:

## Finalization Instructions

1. Set `APP_PROVIDER=gcp` and choose `APP_COMPLEXITY`.
2. Populate Terraform variables for Cloud Run, Vertex AI, Vector Search, Redis, and GCS.
3. Configure Vertex Vector Search restricts for metadata and ACL fields.
4. If `RAG_RETRIEVAL_MODE=hybrid`, pair Vertex Vector Search with a keyword backend and expose `search_hybrid`.
5. If graph mode is selected, add a graph adapter exposing `search_graph_augmented`.
6. Replace header identity with IAP/IAM/JWT validation.
7. Configure Gemini safety settings and Perspective API if used.
8. Replace reference eval stubs with domain regression, safety, retrieval, and ACL leakage tests.
9. Deploy through staging, smoke test, and promote via protected production workflow.

## Production Gate Checklist

- Cloud Run service account is used; no service account key file in production.
- Vertex restricts or backend filters enforce document access before retrieval.
- Secret Manager is used for sensitive values.
- Cloud Monitoring/Trace are configured.
- Canary and smoke tests pass before production promotion.
