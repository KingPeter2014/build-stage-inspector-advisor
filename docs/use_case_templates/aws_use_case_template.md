# AWS Use-Case Finalization Template

Use this when a concrete project chooses AWS Bedrock / ECS / OpenSearch.

## Required Inputs

- Business goal and success metric:
- AWS account, region, and data residency requirement:
- Identity model: Cognito / IAM Identity Center / custom JWT:
- Data sources: S3 / RDS / Kinesis / Glue catalog / custom:
- Corpus sensitivity and compliance requirements:
- RAG retrieval mode: `vector` / `hybrid` / `graph_augmented` / `hybrid_graph`
- RAG security mode: `metadata_filtering` / `acl_filtering` / `policy_enforced_acl`
- OpenSearch index schema, analyzers, and k-NN settings:
- Graph option, if needed: Amazon Neptune / custom graph adapter
- Bedrock models, guardrails, and model access:
- Eval datasets and thresholds:
- Latency, cost, and CloudWatch alarm SLOs:

## Finalization Instructions

1. Set `APP_PROVIDER=aws` and choose `APP_COMPLEXITY`.
2. Populate Terraform variables for VPC, ECS, OpenSearch, Redis, and Bedrock model IDs.
3. Implement OpenSearch hybrid retrieval with BM25 + k-NN when `RAG_RETRIEVAL_MODE=hybrid`.
4. For ACL modes, translate users/groups/tenants into OpenSearch bool filters before retrieval.
5. If graph mode is selected, add a Neptune/custom graph adapter exposing `search_graph_augmented`.
6. Replace header identity with Cognito/JWT/IAM-aware request authentication.
7. Configure Bedrock Guardrails and decide block/redact/escalate policy.
8. Replace reference eval stubs with domain regression, safety, retrieval, and ACL leakage tests.
9. Deploy through staging, smoke test, and promote via protected production workflow.

## Production Gate Checklist

- ECS task role is used; no static AWS access keys in production.
- OpenSearch access policies and filters enforce document access.
- Secrets Manager is used for sensitive values.
- Bedrock model access and guardrails are configured.
- CloudWatch metrics/alarms cover latency, errors, spend, and retrieval leakage tests.
