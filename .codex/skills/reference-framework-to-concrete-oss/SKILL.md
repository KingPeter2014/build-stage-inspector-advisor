---
name: reference-framework-to-concrete-oss
description: Adapt a generic or multi-provider reference framework into a concrete open-source project. Use when Codex needs to remove unused platform/provider targets, keep data-source extensibility, rewire registries/CLIs/tests/docs to a single OSS runtime, preserve useful framework layers, and produce a clear adaptation plan for similar domain-specific projects.
---

# Reference Framework To Concrete OSS

## Overview

Use this skill to convert a broad reference framework into a concrete OSS-first
project without throwing away reusable ingestion, RAG, governance,
observability, or evaluation layers.

The central distinction: remove unwanted runtime/deployment targets, but keep
future data sources as connector boundaries.

## Workflow

### 1. Inventory Before Editing

Map the framework shape first:

- List provider/runtime target directories.
- Search for provider strings in code, tests, docs, CI, Docker, env examples, and IaC.
- Identify stable framework layers worth keeping: `core`, ingestion, storage, RAG, serving, governance, observability, evals.
- Identify concrete-project hints from docs, sample data, open tabs, and user wording.

Prefer `rg --files` and targeted `rg -n` searches. Search both path-style and
import-style references, for example:

```text
providers.azure
providers/aws
deploy_aws
terraform/envs/gcp
Azure
Bedrock
Vertex
```

### 2. Classify Removal Boundaries

Remove:

- Cloud/provider runtime packages that are no longer supported.
- Provider-specific gateway, RAG, agent, storage, model, observability, and governance implementations.
- Provider-specific IaC and deployment workflows.
- Provider-specific use-case templates and README target matrices.
- Tests whose only purpose is validating deleted provider settings.

Keep:

- Generic source connector interfaces.
- Local file ingestion.
- Optional cloud-capable data-source connectors when the user wants future ingestion from cloud storage.
- S3-compatible object-store support if it is framed as MinIO/LocalStack/object storage, not a cloud deployment target.
- RAG mode abstractions when they support future OSS hybrid, graph, ACL, or reranking work.
- Framework maturity/stub policies.

Ask only if deletion would remove a capability the user explicitly wants. In
ambiguous cases, preserve capability at the connector/interface layer and remove
only runtime platform targeting.

### 3. Rewire Runtime To OSS-Only

Update these common surfaces:

- `providers/__init__.py`: supported providers should be `["open_source"]`.
- RAG provider registries: remove factories for deleted providers.
- Ingestion/eval CLIs: keep `--provider` only if compatibility helps, but restrict choices to `open_source`.
- Dockerfile: remove provider build args and route to the OSS gateway only.
- Capability matrices: collapse to open-source implementation and OSS extension options.
- Core interface docstrings: remove deleted provider examples.
- Schema defaults/comments: set `provider` to `open_source`.

Keep `open_source` naming unless the project already has a better runtime name
and renaming is in scope.

### 4. Preserve Data-Source Extensibility

Document and retain future source paths separately from runtime targets:

- Local folders for primary corpora.
- S3-compatible object storage or other cloud storage.
- SharePoint or Microsoft 365 libraries.
- SQL databases.
- Streams.
- Web pages or query-time web search.

Each source should emit the same `RawDocument` contract. Cleaning, chunking,
indexing, retrieval, and eval logic should remain downstream of that boundary.

### 5. Rewrite Public Docs

Make the README describe the concrete project first, then the framework layers.

Include:

- The concrete project purpose.
- The single supported runtime target.
- The retained OSS stack.
- The distinction between data sources and deployment targets.
- Quick start commands.
- Current and future data-source options.
- Next adaptation work: metadata schema, source trust, citation policy, domain prompts, golden evals, ACL rules.

Also update architecture docs, env examples, CI comments, and use-case templates
so they do not continue to advertise deleted platforms.

### 6. Validate The Cleanup

Run at least syntax and stale-reference checks:

```text
python -m py_compile <edited python files>
rg -n -i "<deleted-provider-keywords>"
```

If the test runner is available, run focused unit tests. If not available,
report that clearly and include the syntax checks that did run.

Use git status with a safe-directory override if repository ownership blocks
status inspection:

```text
git -c safe.directory=<absolute-repo-path> status --short
```

## Common Pitfalls

- Do not delete cloud data-source concepts just because cloud deployment targets are removed.
- Do not leave provider choices in CLI args, Docker entrypoints, RAG registries, or tests.
- Do not keep docs that imply multi-cloud parity after code removal.
- Do not treat LocalStack or S3-compatible object storage as a runtime platform; describe it as a storage/source test double.
- Do not remove user data or sample corpora while searching for provider keywords.

## Completion Criteria

The adaptation cleanup is complete when:

- Only the intended runtime provider remains.
- Stale imports to removed providers are gone.
- Docker and scripts start the OSS runtime path.
- Public docs explain the concrete project and source extensibility.
- Env examples no longer advertise deleted runtime platforms.
- Syntax checks pass, and tests either pass or the missing test dependency is reported.
