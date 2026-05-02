"""Azure RAG retriever factory.

Azure AI Search supports vector and hybrid keyword+vector retrieval. Optional
graph augmentation should be supplied through a project-specific graph adapter
such as Cosmos DB Gremlin, Neo4j, or Azure SQL graph patterns.
"""
from __future__ import annotations

from typing import Any

from serving.rag.retriever import GenericRAGRetriever


def build_rag_retriever(backend: Any | None = None) -> GenericRAGRetriever:
    if backend is None:
        from providers.azure.storage.ai_search_store import AzureAISearchStore
        backend = AzureAISearchStore(use_hybrid=True)
    return GenericRAGRetriever("azure", backend)
