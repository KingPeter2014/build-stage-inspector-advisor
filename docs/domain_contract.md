# Build Stage Advisor Domain Contract

## V1 Scope

Build Stage Inspector Advisor provides source-grounded construction-stage inspection advice for Australian domestic and building-stage workflows. The first corpus is local documents under `data/raw_docs`, with NCC and other authoritative regulation material as the primary source class.

The advisor may use contracts, standards, guidance, reports, policies, project files, web pages, SharePoint libraries, SQL sources, and streams after those sources emit the same document metadata contract. Until a source is ingested and retrievable, the advisor must say that it does not have enough evidence.

## Corpus Assumptions

- Regulations and standards are authoritative for code-style requirements.
- Contracts and project documents are private unless explicitly marked public or filtered by tenant/ACL metadata.
- Web-derived material is unverified unless the source policy promotes it to authoritative or external.
- Advice is informational and inspection-oriented; it must not claim to replace a certifier, lawyer, engineer, or other required professional.

## Inspection Stages

Use these v1 `inspection_stage` values in metadata filters and evals:

```text
site_prep
slab
frame
lockup
waterproofing
fixing
practical_completion
handover
other
```

## Metadata Filters

The public RAG request keeps using `filter_by`. Supported v1 keys are:

```text
document_type
inspection_stage
jurisdiction
building_class
tenant_id
project_id
contract_id
document_family
source_version
trust_level
tags
```

ACL constraints use `acl_filter` with:

```text
acl_user_ids
acl_group_ids
tenant_id
document_id
```

Private project and contract documents must be filtered before or during retrieval. Post-retrieval filtering is not acceptable for sensitive records.

## Answer Contract

Advisor answers must:

- use only retrieved context;
- cite each material source using `source_title` plus `clause`, `section`, or `volume` when present;
- distinguish regulation, standard, contract, project, and web evidence when that metadata is available;
- state when retrieved sources conflict;
- say "I don't know based on the provided sources" when the answer is not supported;
- avoid legal, engineering, certification, or safety determinations that require a qualified professional.

## Advisor Skills

The v1 advisor should be evaluated on these skills:

- identify the inspection stage and retrieve relevant stage evidence;
- separate NCC/code compliance from contract payment obligations;
- cite Deemed-to-Satisfy provisions and source titles when making code-oriented observations;
- check Victorian 7-star/NatHERS and Whole-of-Home evidence without treating marketing material as compliance proof;
- apply tenant and ACL constraints before retrieval for private project or contract documents;
- refuse certification, legal conclusions, and unsupported compliance claims.
