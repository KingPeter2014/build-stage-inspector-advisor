"""AWS RAG retriever factory.

OpenSearch is the default backend. Hybrid retrieval can be implemented with a
BM25 + k-NN query composition in a backend exposing `search_hybrid`. Optional
graph augmentation should be supplied through Neptune or a custom graph adapter.
"""
from __future__ import annotations

from typing import Any

from serving.rag.retriever import GenericRAGRetriever


def build_rag_retriever(backend: Any | None = None) -> GenericRAGRetriever:
    if backend is None:
        from providers.aws.storage.opensearch_store import OpenSearchVectorStore
        backend = OpenSearchVectorStore()
    return GenericRAGRetriever("aws", backend)
