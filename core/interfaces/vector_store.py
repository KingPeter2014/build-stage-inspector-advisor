"""
core/interfaces/vector_store.py
Abstract vector store contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class VectorSearchResult:
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


class AbstractVectorStore(ABC):
    """
    Uniform interface for all vector store backends.
    Implementations: Qdrant (OSS), Azure AI Search, Amazon OpenSearch, Vertex AI Vector Search.
    """

    @abstractmethod
    def upsert_chunks(self, chunks: list) -> None:
        """Embed and upsert a list of Chunk objects."""

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_by: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Return top-k semantically similar chunks."""

    @abstractmethod
    def delete_by_document(self, document_id: str) -> None:
        """Remove all chunks belonging to a document."""
