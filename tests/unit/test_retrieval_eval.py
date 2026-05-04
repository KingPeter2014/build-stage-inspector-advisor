import json

import pytest

from model_development.evaluation.retrieval_eval import (
    RetrievedEvidence,
    RetrievalGoldSample,
    build_retrieval_filter,
    citation_hit,
    evaluate_retrieval_samples,
    load_retrieval_gold,
    validate_gold_dataset,
)


def test_load_retrieval_gold_reads_jsonl_samples(tmp_path):
    path = tmp_path / "gold.jsonl"
    row = {
        "input": "question",
        "expected_output": "criteria",
        "retrieval_context": ["NCC waterproofing evidence"],
        "metadata": {
            "category": "dts_waterproofing",
            "inspection_stage": "waterproofing",
            "document_type": "regulation",
            "jurisdiction": "VIC",
            "required_citations": ["NCC Housing Provisions Part 10.2"],
        },
    }
    path.write_text(json.dumps(row) + "\n")

    samples = load_retrieval_gold(path)

    assert samples[0].input == "question"
    assert samples[0].required_citations == ["NCC Housing Provisions Part 10.2"]


def test_build_retrieval_filter_supports_none_domain_and_strict_modes():
    metadata = {
        "document_type": "contract",
        "inspection_stage": "lockup",
        "jurisdiction": "VIC",
        "building_class": "1",
        "contract_type": "build_all_stages",
    }

    assert build_retrieval_filter(metadata, "none") == {}
    assert build_retrieval_filter(metadata, "domain") == {
        "inspection_stage": "lockup",
        "jurisdiction": "VIC",
        "building_class": "1",
    }
    assert build_retrieval_filter(metadata, "strict") == metadata
    with pytest.raises(ValueError):
        build_retrieval_filter(metadata, "surprise")


def test_citation_hit_matches_source_title_and_locator_metadata():
    result = RetrievedEvidence(
        document_id="doc-1",
        content="Wet area waterproofing rules.",
        metadata={
            "source_title": "NCC Housing Provisions",
            "section": "Part 10.2",
        },
    )

    assert citation_hit("NCC Housing Provisions Part 10.2", [result]) is True


def test_evaluate_retrieval_samples_scores_hits_and_skips_refusal_cases():
    samples = [
        RetrievalGoldSample(
            input="waterproofing?",
            expected_output="criteria",
            retrieval_context=["NCC Housing Provisions Part 10.2 wet area waterproofing"],
            metadata={
                "category": "dts_waterproofing",
                "inspection_stage": "waterproofing",
                "document_type": "regulation",
                "jurisdiction": "VIC",
                "required_citations": ["NCC Housing Provisions Part 10.2"],
            },
        ),
        RetrievalGoldSample(
            input="private tenant defect?",
            expected_output="refuse",
            retrieval_context=["private tenant-b defect list"],
            metadata={
                "category": "acl_leakage",
                "inspection_stage": "handover",
                "document_type": "report",
                "jurisdiction": "VIC",
                "must_refuse": True,
            },
        ),
    ]

    def retrieve(query, filter_by, top_k):
        assert query == "waterproofing?"
        assert top_k == 5
        return [
            RetrievedEvidence(
                document_id="doc-1",
                content="NCC Housing Provisions Part 10.2 wet area waterproofing",
                score=0.9,
                metadata={"source_title": "NCC Housing Provisions", "section": "Part 10.2"},
            )
        ]

    report = evaluate_retrieval_samples(samples, retrieve)

    assert report["evaluated"] == 1
    assert report["skipped"] == 1
    assert report["recall_at_k"] == 1.0
    assert report["cases"][1]["status"] == "skipped"


def test_validate_gold_dataset_requires_citations_for_non_refusal_cases():
    report = validate_gold_dataset([
        RetrievalGoldSample(
            input="q",
            expected_output="a",
            retrieval_context=["context"],
            metadata={
                "category": "stage",
                "inspection_stage": "frame",
                "document_type": "guidance",
                "jurisdiction": "VIC",
            },
        )
    ])

    assert report["failed"] == 1
    assert "required citations" in report["failures"][0]["reason"]
