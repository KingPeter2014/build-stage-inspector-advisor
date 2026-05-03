"""
RAG configuration and capability metadata.

The runtime target is open source. Retrieval still supports optional extensions
such as hybrid search, graph augmentation, reranking, and ACL-aware filters.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

from core.framework import FrameworkMode, get_framework_mode


class RAGRetrievalMode(str, Enum):
    VECTOR = "vector"
    HYBRID = "hybrid"
    GRAPH_AUGMENTED = "graph_augmented"
    HYBRID_GRAPH = "hybrid_graph"

    @property
    def requires_graph(self) -> bool:
        return self in {RAGRetrievalMode.GRAPH_AUGMENTED, RAGRetrievalMode.HYBRID_GRAPH}


class RAGSecurityMode(str, Enum):
    NONE = "none"
    METADATA_FILTERING = "metadata_filtering"
    ACL_FILTERING = "acl_filtering"
    POLICY_ENFORCED_ACL = "policy_enforced_acl"

    @property
    def requires_acl_filter(self) -> bool:
        return self in {RAGSecurityMode.ACL_FILTERING, RAGSecurityMode.POLICY_ENFORCED_ACL}


@dataclass(frozen=True)
class RAGOptions:
    retrieval_mode: RAGRetrievalMode = RAGRetrievalMode.VECTOR
    security_mode: RAGSecurityMode = RAGSecurityMode.NONE
    graph_enabled: bool = False
    reranker_enabled: bool = False
    framework_mode: FrameworkMode = FrameworkMode.REFERENCE

    @classmethod
    def from_env(cls) -> "RAGOptions":
        return cls(
            retrieval_mode=RAGRetrievalMode(os.getenv("RAG_RETRIEVAL_MODE", "vector")),
            security_mode=RAGSecurityMode(os.getenv("RAG_SECURITY_MODE", "none")),
            graph_enabled=os.getenv("GRAPH_ENABLED", "false").lower() in ("1", "true", "yes"),
            reranker_enabled=os.getenv("RERANKER_ENABLED", "false").lower() in ("1", "true", "yes"),
            framework_mode=get_framework_mode(),
        )

    def validate(self) -> None:
        if self.retrieval_mode.requires_graph and not self.graph_enabled:
            raise ValueError(
                f"RAG_RETRIEVAL_MODE={self.retrieval_mode.value} requires GRAPH_ENABLED=true."
            )
        if self.framework_mode.is_production_path and self.security_mode == RAGSecurityMode.NONE:
            raise ValueError(
                "Production RAG paths should use at least metadata_filtering. "
                "Set RAG_SECURITY_MODE explicitly if the corpus is intentionally public."
            )


@dataclass(frozen=True)
class ProviderRAGCapability:
    provider: str
    vector: str
    hybrid: str
    graph: str
    metadata_filtering: str
    acl_filtering: str
    reranking: str
    notes: str = ""


RAG_CAPABILITY_MATRIX: dict[str, ProviderRAGCapability] = {
    "open_source": ProviderRAGCapability(
        provider="open_source",
        vector="implemented: Qdrant",
        hybrid="external option: Qdrant hybrid configuration or an OSS keyword backend",
        graph="external option: Neo4j, ArangoDB, or Memgraph adapter",
        metadata_filtering="implemented via vector-store filters where supported",
        acl_filtering="framework option: pre-retrieval metadata/ACL filters required for secure apps",
        reranking="external option: cross-encoder or managed reranker",
    ),
}


def build_acl_filter(
    *,
    user_id: str | None = None,
    groups: list[str] | None = None,
    tenant_id: str | None = None,
    allowed_document_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Build a provider-neutral ACL filter payload.

    Retrieval adapters may translate this into Qdrant filters, keyword-backend
    filters, object metadata constraints, or graph traversal constraints.
    """
    acl: dict[str, Any] = {}
    if user_id:
        acl["acl_user_ids"] = user_id
    if groups:
        acl["acl_group_ids"] = groups
    if tenant_id:
        acl["tenant_id"] = tenant_id
    if allowed_document_ids:
        acl["document_id"] = allowed_document_ids
    return acl


def merge_retrieval_filters(
    metadata_filter: dict[str, Any] | None,
    acl_filter: dict[str, Any] | None,
) -> dict[str, Any] | None:
    merged: dict[str, Any] = {}
    if metadata_filter:
        merged.update(metadata_filter)
    if acl_filter:
        merged.update(acl_filter)
    return merged or None
