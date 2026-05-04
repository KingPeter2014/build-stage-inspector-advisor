"""
Canonical document metadata shared by ingestion, retrieval, and agents.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    REGULATION = "regulation"
    CONTRACT = "contract"
    POLICY = "policy"
    LEGAL = "legal"
    STANDARD = "standard"
    GUIDANCE = "guidance"
    REPORT = "report"
    WEB = "web"
    OTHER = "other"


class TrustLevel(str, Enum):
    AUTHORITATIVE = "authoritative"
    INTERNAL = "internal"
    EXTERNAL = "external"
    UNVERIFIED = "unverified"


class DocumentMetadata(BaseModel):
    """
    Stable metadata payload for heterogeneous knowledge-base documents.

    Fields are intentionally broad enough for NCC volumes, domestic building
    contracts, policies, legal material, SharePoint files, and web documents.
    """

    document_type: DocumentType = DocumentType.OTHER
    source_type: str = "unstructured"
    source_uri: str = ""
    source_title: str = ""
    source_version: str = ""
    retrieved_at: datetime | None = None
    document_family: str = ""
    jurisdiction: str = ""
    effective_date: date | None = None

    section: str = ""
    clause: str = ""
    volume: str = ""
    building_class: str = ""
    inspection_stage: str = ""

    project_id: str = ""
    contract_id: str = ""
    tenant_id: str = ""
    acl_user_ids: list[str] = Field(default_factory=list)
    acl_group_ids: list[str] = Field(default_factory=list)

    trust_level: TrustLevel = TrustLevel.UNVERIFIED
    tags: list[str] = Field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        """Return a Qdrant-safe payload without empty values."""
        payload: dict[str, Any] = {}
        for key, value in self.model_dump().items():
            if value in (None, "", []):
                continue
            if isinstance(value, (date, datetime)):
                payload[key] = value.isoformat()
            elif isinstance(value, Enum):
                payload[key] = value.value
            else:
                payload[key] = value
        return payload
