"""
Deterministic retrieval evaluation helpers for the domain gold dataset.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


DOMAIN_FILTER_KEYS = (
    "document_type",
    "inspection_stage",
    "jurisdiction",
    "building_class",
    "contract_type",
)


@dataclass(frozen=True)
class RetrievalGoldSample:
    input: str
    expected_output: str
    retrieval_context: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def required_citations(self) -> list[str]:
        return [str(item) for item in self.metadata.get("required_citations", [])]

    @property
    def must_refuse(self) -> bool:
        return bool(self.metadata.get("must_refuse", False))


@dataclass(frozen=True)
class RetrievedEvidence:
    document_id: str = ""
    content: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


def load_retrieval_gold(path: str | Path) -> list[RetrievalGoldSample]:
    samples = []
    for line in Path(path).read_text().splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        samples.append(RetrievalGoldSample(
            input=data["input"],
            expected_output=data["expected_output"],
            retrieval_context=list(data.get("retrieval_context") or []),
            metadata=dict(data.get("metadata") or {}),
        ))
    return samples


def build_retrieval_filter(
    metadata: dict[str, Any],
    strategy: str = "none",
) -> dict[str, Any]:
    if strategy == "none":
        return {}
    if strategy not in {"domain", "strict"}:
        raise ValueError("filter strategy must be one of: none, domain, strict")

    keys = ("inspection_stage", "jurisdiction", "building_class")
    if strategy == "strict":
        keys = DOMAIN_FILTER_KEYS

    return {
        key: metadata[key]
        for key in keys
        if metadata.get(key) not in ("", None, [], "other")
    }


def evidence_text(evidence: RetrievedEvidence) -> str:
    metadata = evidence.metadata or {}
    parts = [
        evidence.document_id,
        evidence.content,
        str(metadata.get("source_title", "")),
        str(metadata.get("filename", "")),
        str(metadata.get("source_uri", "")),
        str(metadata.get("clause", "")),
        str(metadata.get("section", "")),
        str(metadata.get("volume", "")),
        " ".join(str(tag) for tag in metadata.get("tags", []) or []),
    ]
    return " ".join(part for part in parts if part).lower()


def citation_hit(required_citation: str, results: Iterable[RetrievedEvidence]) -> bool:
    needle_tokens = [
        token
        for token in required_citation.lower().replace("/", " ").split()
        if len(token) >= 3
    ]
    if not needle_tokens:
        return False
    for result in results:
        haystack = evidence_text(result)
        if all(token in haystack for token in needle_tokens[:4]):
            return True
    return False


def context_hit(sample: RetrievalGoldSample, results: Iterable[RetrievedEvidence]) -> bool:
    context_tokens = set()
    for context in sample.retrieval_context:
        context_tokens.update(
            token
            for token in context.lower().replace("/", " ").split()
            if len(token) >= 5
        )
    if not context_tokens:
        return False

    for result in results:
        result_tokens = set(
            token
            for token in evidence_text(result).replace("/", " ").split()
            if len(token) >= 5
        )
        overlap = context_tokens.intersection(result_tokens)
        if len(overlap) >= min(5, len(context_tokens)):
            return True
    return False


def evaluate_retrieval_samples(
    samples: list[RetrievalGoldSample],
    retrieve: Callable[[str, dict[str, Any], int], list[RetrievedEvidence]],
    *,
    top_k: int = 5,
    filter_strategy: str = "none",
) -> dict[str, Any]:
    cases = []
    passed = 0
    evaluated = 0
    skipped = 0

    for sample in samples:
        filter_by = build_retrieval_filter(sample.metadata, filter_strategy)
        if sample.must_refuse:
            skipped += 1
            cases.append({
                "input": sample.input,
                "status": "skipped",
                "reason": "policy/refusal case; covered by safety and ACL leakage tests",
                "filter_by": filter_by,
            })
            continue

        results = retrieve(sample.input, filter_by, top_k)
        required = sample.required_citations
        hit_count = sum(1 for citation in required if citation_hit(citation, results))
        has_context_hit = context_hit(sample, results)
        passed_case = bool(results) and (hit_count > 0 or has_context_hit or not required)
        evaluated += 1
        passed += int(passed_case)

        cases.append({
            "input": sample.input,
            "status": "passed" if passed_case else "failed",
            "filter_by": filter_by,
            "required_citations": required,
            "citation_hits": hit_count,
            "context_hit": has_context_hit,
            "top_score": max((result.score for result in results), default=0.0),
            "top_sources": [
                {
                    "document_id": result.document_id,
                    "score": result.score,
                    "source_title": result.metadata.get("source_title", ""),
                    "filename": result.metadata.get("filename", ""),
                    "clause": result.metadata.get("clause", ""),
                    "section": result.metadata.get("section", ""),
                    "volume": result.metadata.get("volume", ""),
                }
                for result in results[:3]
            ],
        })

    recall_at_k = passed / max(evaluated, 1)
    return {
        "suite": "rag_retrieval",
        "status": "evaluated",
        "top_k": top_k,
        "filter_strategy": filter_strategy,
        "total": len(samples),
        "evaluated": evaluated,
        "skipped": skipped,
        "passed": passed,
        "failed": evaluated - passed,
        "recall_at_k": recall_at_k,
        "cases": cases,
    }


def validate_gold_dataset(samples: list[RetrievalGoldSample]) -> dict[str, Any]:
    failures = []
    for index, sample in enumerate(samples, start=1):
        metadata = sample.metadata
        for key in ("category", "inspection_stage", "document_type", "jurisdiction"):
            if not metadata.get(key):
                failures.append({"row": index, "reason": f"missing metadata.{key}"})
        if not sample.must_refuse and not sample.required_citations:
            failures.append({"row": index, "reason": "non-refusal case has no required citations"})
        if not sample.retrieval_context:
            failures.append({"row": index, "reason": "missing retrieval_context"})

    total = len(samples)
    failed = len(failures)
    return {
        "suite": "rag_retrieval",
        "status": "dataset-validated",
        "total": total,
        "passed": total - failed,
        "failed": failed,
        "pass_rate": (total - failed) / max(total, 1),
        "failures": failures,
    }
