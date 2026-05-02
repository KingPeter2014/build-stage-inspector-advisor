"""
Provider-neutral RAG retriever contract.

Retrievers are responsible for applying metadata/ACL filters during retrieval.
They may implement vector, hybrid, graph-augmented, or hybrid+graph retrieval
depending on provider capability and project configuration.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.interfaces.vector_store import VectorSearchResult
from core.rag import RAGRetrievalMode, RAGSecurityMode


@dataclass(frozen=True)
class RetrievalRequest:
    query: str
    top_k: int = 5
    retrieval_mode: RAGRetrievalMode = RAGRetrievalMode.VECTOR
    security_mode: RAGSecurityMode = RAGSecurityMode.NONE
    metadata_filter: dict[str, Any] | None = None
    acl_filter: dict[str, Any] | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResponse:
    results: list[VectorSearchResult]
    provider: str
    retrieval_mode: RAGRetrievalMode
    security_mode: RAGSecurityMode
    filter_applied: bool
    acl_applied: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractRAGRetriever(ABC):
    """Uniform interface for RAG retrieval backends."""

    @abstractmethod
    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        """Retrieve context chunks with required filters applied."""

    @abstractmethod
    def supports(self, retrieval_mode: RAGRetrievalMode) -> bool:
        """Return whether this retriever supports the requested retrieval mode."""
