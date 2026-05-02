"""Open-source RAG retriever factory."""
from __future__ import annotations

from serving.rag.retriever import GenericRAGRetriever
from storage.vector_store.qdrant_store import QdrantVectorStore


def build_rag_retriever(vector_store: QdrantVectorStore | None = None) -> GenericRAGRetriever:
    """Build the default OSS retriever around Qdrant or a supplied backend."""
    return GenericRAGRetriever("open_source", vector_store or QdrantVectorStore())
