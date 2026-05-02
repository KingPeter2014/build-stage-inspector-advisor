"""GCP RAG retriever factory.

Vertex AI Vector Search is the default backend. Hybrid retrieval normally pairs
Vertex Vector Search with a separate keyword backend or BigQuery search pattern.
Graph augmentation should be supplied through a project-specific graph adapter.
"""
from __future__ import annotations

from typing import Any

from serving.rag.retriever import GenericRAGRetriever


def build_rag_retriever(backend: Any | None = None) -> GenericRAGRetriever:
    if backend is None:
        from providers.gcp.storage.vertex_vector_search import VertexVectorSearch
        backend = VertexVectorSearch()
    return GenericRAGRetriever("gcp", backend)
