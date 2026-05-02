# Azure Use-Case Finalization Template

Use this when a concrete project chooses Azure AI Foundry / Azure OpenAI.

## Required Inputs

- Business goal and success metric:
- Azure subscription, region, and data residency requirement:
- Entra ID tenant, app roles, groups, and identity flow:
- Data sources: ADLS / SharePoint / SQL / Teams / custom:
- Corpus sensitivity and compliance requirements:
- RAG retrieval mode: `vector` / `hybrid` / `graph_augmented` / `hybrid_graph`
- RAG security mode: `metadata_filtering` / `acl_filtering` / `policy_enforced_acl`
- Azure AI Search index schema and semantic ranker requirement:
- Graph option, if needed: Cosmos DB Gremlin / Neo4j / Azure SQL graph pattern
- Azure OpenAI deployments and quota:
- Eval datasets and thresholds:
- Latency, cost, and content safety SLOs:

## Finalization Instructions

1. Set `APP_PROVIDER=azure` and choose `APP_COMPLEXITY`.
2. Populate Terraform variables for region, capacity, replicas, private networking, and managed identity.
3. Align Azure AI Search fields with metadata and ACL requirements.
4. Use Azure AI Search hybrid retrieval for `RAG_RETRIEVAL_MODE=hybrid`.
5. For ACL modes, filter on Entra user/group/tenant fields during Azure AI Search retrieval.
6. If graph mode is selected, add a graph adapter exposing `search_graph_augmented`.
7. Replace header identity with Entra ID JWT/OIDC validation.
8. Configure Azure Content Safety and decide block/redact/escalate policy.
9. Replace reference eval stubs with domain regression, safety, retrieval, and ACL leakage tests.
10. Deploy through staging, smoke test, and promote via protected production workflow.

## Production Gate Checklist

- Managed Identity is used; no client secret in production.
- Azure AI Search filters enforce document access before retrieval.
- Key Vault references are used for secrets.
- Content Safety and audit logging are enabled.
- Production GitHub Environment requires approval.
