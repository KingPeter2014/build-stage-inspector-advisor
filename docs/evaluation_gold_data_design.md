# Victoria Domain MVP Gold Evaluation Data

## Purpose

This gold set is for deterministic and model-backed evaluation of Build Stage Inspector Advisor. It checks whether answers stay grounded in retrieved NCC, Victorian stage-inspection, and domestic building contract sources.

The expected outputs are written as answer criteria rather than long canonical prose. This makes the tests robust to wording differences while still checking the behaviours that matter: source use, stage awareness, Deemed-to-Satisfy reasoning, contract/payment constraints, and refusal when evidence is missing.

## Source Anchors

Use official source documents when building retrieval fixtures:

- NCC 2022 Volume Two and Housing Provisions for Class 1 and 10 work, including Section H and Housing Provisions Part 10.2.
- NCC 2022 Victoria Part H6 for energy-efficiency pathways and Victorian variations.
- ABCB Specification 42 for the 7-star house energy rating software pathway.
- Victorian Government 7-star energy efficiency standards, including the 1 May 2024 mandatory commencement date.
- Victorian Building Authority mandatory notification stage guidance.
- Consumer Affairs Victoria domestic building contract, building stage, deposit, and progress payment guidance.

## Gold Data Shape

Each JSONL record should include:

- `input`: the user question.
- `expected_output`: criteria the answer must satisfy.
- `retrieval_context`: compact source snippets to simulate retrieved context.
- `metadata`: domain labels for filtering and eval reporting.

Recommended metadata keys:

```text
category
inspection_stage
contract_type
document_type
jurisdiction
building_class
code_focus
payment_focus
required_citations
must_refuse
```

## Coverage Matrix

The curated set in `data/eval_datasets/regression_golden.jsonl` covers:

- Site prep / pre-start: permit, approved plans, contract scope, domestic building insurance, and 7-star documentation.
- Base / slab: footing or slab stage completion, mandatory inspection, and progress payment limits.
- Frame: building surveyor approval before frame payment.
- Lock-up: envelope completion, weatherproofing cues, and lock-up contract payment differences.
- Waterproofing: NCC DTS wet-area requirements, AS 3740, penetrations, floor wastes, and missing-evidence refusal.
- Fixing: internal fitting stage, wet-area evidence, and build-to-fixing payment terms.
- Practical completion / final: occupancy permit or certificate of final inspection, defects, and final payment.
- Handover: records, warranties, energy reports, inspection outcomes, and private-document ACL refusal.

## Evaluation Rules

An answer should pass only if it:

- uses retrieved context and names the cited source title plus clause, section, volume, practice note, or page label where available;
- separates NCC/code compliance from contract/payment obligations;
- treats 7-star/NatHERS and Whole-of-Home evidence as compliance documents, not casual marketing claims;
- avoids certifying compliance, safety, engineering adequacy, or legal entitlement unless the source explicitly supports that limited statement;
- refuses or says it does not know when source evidence is absent.

## Advisor Skills Exercised

The gold set is designed to test these skills:

- stage inspection triage across site prep, slab, frame, lock-up, waterproofing, fixing, practical completion, and handover;
- Deemed-to-Satisfy evidence retrieval for NCC waterproofing, damp/weatherproofing, structure, and energy-efficiency topics;
- contract-stage reasoning across build-all-stages, build-to-lock-up, build-to-fixing, cost-plus renovation, and display-home upgrade scenarios;
- 7-star NatHERS and Whole-of-Home evidence handling for Victorian permits from 1 May 2024 onward;
- citation discipline, especially separating NCC/code evidence from Consumer Affairs Victoria contract/payment guidance;
- refusal behaviour for missing evidence, private documents, structural certification, and legal/payment entitlement questions.

## Commands

Ingest the official Victoria web sources used by the gold set:

```powershell
python scripts/run_ingestion.py --source-type web --web-manifest data/web_sources/official_vic_sources.json
```

Validate the curated gold dataset without touching Qdrant:

```powershell
python scripts/run_evals.py --suite rag_retrieval
```

After indexing documents, run the live Qdrant retrieval gate:

```powershell
python scripts/run_evals.py --suite rag_retrieval --live-retrieval --top-k 5
```

Apply metadata filters only after ingestion metadata is populated consistently:

```powershell
python scripts/run_evals.py --suite rag_retrieval --live-retrieval --retrieval-filter-strategy domain
```

Use `--retrieval-filter-strategy strict` only when document type, inspection
stage, jurisdiction, building class, and contract type are reliably present in
chunk payloads.

## Next Data Additions

- Add fixture documents under `data/raw_docs` with stable source metadata for NCC clauses, VBA practice notes, CAV contract pages, and sample contract clauses.
- Review `reports/rag_retrieval_report.json` after live runs and add missing source snippets or metadata where recall is weak.
- Add adversarial tests for private contract leakage across tenants and for questions that try to convert advisory output into certification.
