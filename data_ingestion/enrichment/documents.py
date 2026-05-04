"""
Document metadata enrichment for local, cloud, SharePoint, and web sources.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.schemas.document import DocumentMetadata, DocumentType, TrustLevel


_YEAR_RE = re.compile(r"\b(20\d{2}|19\d{2})\b")


def _title_from_source(source: str, metadata: dict[str, Any]) -> str:
    filename = metadata.get("filename")
    if filename:
        return Path(str(filename)).stem
    return Path(source).stem or source


def _infer_document_type(text: str) -> DocumentType:
    lowered = text.lower()
    if "ncc" in lowered or "national construction code" in lowered:
        return DocumentType.REGULATION
    if "contract" in lowered or "agreement" in lowered:
        return DocumentType.CONTRACT
    if "policy" in lowered or "procedure" in lowered:
        return DocumentType.POLICY
    if "legislation" in lowered or "legal" in lowered or "act " in lowered:
        return DocumentType.LEGAL
    if "standard" in lowered:
        return DocumentType.STANDARD
    if lowered.startswith(("http://", "https://")):
        return DocumentType.WEB
    return DocumentType.OTHER


def _infer_volume(title: str) -> str:
    match = re.search(r"\bVolume\s+(One|Two|Three|[1-9]\d*)\b", title, re.IGNORECASE)
    return match.group(0) if match else ""


def enrich_document_metadata(
    source: str,
    metadata: dict[str, Any] | None = None,
    source_type: str = "unstructured",
) -> dict[str, Any]:
    """
    Enrich raw connector metadata with canonical document fields.

    Existing caller-provided metadata wins for business identifiers and ACLs,
    while inferred canonical fields fill gaps for retrieval filters and source
    citation.
    """
    base = dict(metadata or {})
    title = str(base.get("source_title") or _title_from_source(source, base))
    search_text = f"{source} {title}"
    doc_type = DocumentType(base.get("document_type") or _infer_document_type(search_text))
    year = _YEAR_RE.search(search_text)

    document_family = str(base.get("document_family") or "")
    trust_level = TrustLevel(base.get("trust_level") or TrustLevel.UNVERIFIED)
    tags = list(base.get("tags") or [])

    if "ncc" in search_text.lower():
        document_family = document_family or "NCC"
        trust_level = TrustLevel(base.get("trust_level") or TrustLevel.AUTHORITATIVE)
        if "ncc" not in tags:
            tags.append("ncc")
    elif "abcb" in search_text.lower():
        document_family = document_family or "ABCB"
        trust_level = TrustLevel(base.get("trust_level") or TrustLevel.AUTHORITATIVE)
        if "abcb" not in tags:
            tags.append("abcb")

    inferred = DocumentMetadata(
        document_type=doc_type,
        source_type=str(base.get("source_type") or source_type),
        source_uri=str(base.get("source_uri") or source),
        source_title=title,
        source_version=str(base.get("source_version") or (year.group(1) if year else "")),
        document_family=document_family,
        jurisdiction=str(base.get("jurisdiction") or ""),
        section=str(base.get("section") or ""),
        clause=str(base.get("clause") or ""),
        volume=str(base.get("volume") or _infer_volume(title)),
        building_class=str(base.get("building_class") or ""),
        inspection_stage=str(base.get("inspection_stage") or ""),
        project_id=str(base.get("project_id") or ""),
        contract_id=str(base.get("contract_id") or ""),
        tenant_id=str(base.get("tenant_id") or ""),
        acl_user_ids=list(base.get("acl_user_ids") or []),
        acl_group_ids=list(base.get("acl_group_ids") or []),
        trust_level=trust_level,
        tags=tags,
    ).to_payload()

    return {**base, **inferred}
