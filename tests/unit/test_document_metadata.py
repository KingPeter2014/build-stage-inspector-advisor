from datetime import date

from core.schemas.document import DocumentMetadata, DocumentType, TrustLevel
from data_ingestion.enrichment import enrich_document_metadata


def test_ncc_volume_metadata_is_inferred_for_retrieval_filters():
    metadata = enrich_document_metadata(
        source="data/raw_docs/NCC 2022/NCC 2022 Volume One.pdf",
        metadata={"filename": "NCC 2022 Volume One.pdf", "suffix": ".pdf"},
    )

    assert metadata["document_type"] == DocumentType.REGULATION.value
    assert metadata["document_family"] == "NCC"
    assert metadata["source_version"] == "2022"
    assert metadata["source_title"] == "NCC 2022 Volume One"
    assert metadata["volume"] == "Volume One"
    assert metadata["trust_level"] == TrustLevel.AUTHORITATIVE.value
    assert "ncc" in metadata["tags"]


def test_contract_metadata_preserves_business_and_acl_fields():
    metadata = enrich_document_metadata(
        source="contracts/domestic-building-contract.md",
        metadata={
            "filename": "domestic-building-contract.md",
            "contract_id": "dbc-001",
            "tenant_id": "client-a",
            "acl_group_ids": ["inspectors"],
        },
    )

    assert metadata["document_type"] == DocumentType.CONTRACT.value
    assert metadata["contract_id"] == "dbc-001"
    assert metadata["tenant_id"] == "client-a"
    assert metadata["acl_group_ids"] == ["inspectors"]


def test_policy_and_legal_documents_fit_same_schema():
    policy = enrich_document_metadata(
        source="sharepoint://operations/site-safety-policy.pdf",
        metadata={"filename": "site-safety-policy.pdf"},
    )
    legal = enrich_document_metadata(
        source="https://example.org/building-act-1993",
        metadata={"source_title": "Building Act 1993"},
        source_type="web",
    )

    assert policy["document_type"] == DocumentType.POLICY.value
    assert legal["document_type"] == DocumentType.LEGAL.value
    assert legal["source_type"] == "web"
    assert legal["source_version"] == "1993"


def test_document_payload_drops_empty_values_and_serializes_dates():
    metadata = DocumentMetadata(
        document_type=DocumentType.POLICY,
        source_title="Policy",
        effective_date=date(2026, 5, 3),
        tags=[],
    ).to_payload()

    assert metadata == {
        "document_type": "policy",
        "source_type": "unstructured",
        "source_title": "Policy",
        "effective_date": "2026-05-03",
        "trust_level": "unverified",
    }
