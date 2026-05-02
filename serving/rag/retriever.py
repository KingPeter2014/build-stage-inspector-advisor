"""
Generic RAG retriever adapter around vector-store-like backends.

Backends can opt into richer modes by exposing:
  - search_hybrid(query, top_k, filter_by)
  - search_graph_augmented(query, top_k, filter_by)
"""
from __future__ import annotations

from typing import Any

from core.framework import decide_stub
from core.interfaces.rag_retriever import (
    AbstractRAGRetriever,
    RetrievalRequest,
    RetrievalResponse,
)
from core.rag import RAGRetrievalMode, merge_retrieval_filters


class GenericRAGRetriever(AbstractRAGRetriever):
    def __init__(self, provider: str, backend: Any) -> None:
        self.provider = provider
        self.backend = backend

    def supports(self, retrieval_mode: RAGRetrievalMode) -> bool:
        if retrieval_mode == RAGRetrievalMode.VECTOR:
            return hasattr(self.backend, "search")
        if retrieval_mode == RAGRetrievalMode.HYBRID:
            return hasattr(self.backend, "search_hybrid") or hasattr(self.backend, "search")
        if retrieval_mode.requires_graph:
            return hasattr(self.backend, "search_graph_augmented")
        return False

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        filter_by = merge_retrieval_filters(request.metadata_filter, request.acl_filter)
        mode = request.retrieval_mode

        if mode.requires_graph and not hasattr(self.backend, "search_graph_augmented"):
            decision = decide_stub(f"RAG {mode.value} retrieval")
            if not decision.allowed:
                raise RuntimeError(decision.reason)
            results = self.backend.search(request.query, top_k=request.top_k, filter_by=filter_by)
            return self._response(request, results, filter_by, {"stubbed_graph": True})

        if mode.requires_graph:
            results = self.backend.search_graph_augmented(
                request.query, top_k=request.top_k, filter_by=filter_by
            )
            return self._response(request, results, filter_by)

        if mode == RAGRetrievalMode.HYBRID and hasattr(self.backend, "search_hybrid"):
            results = self.backend.search_hybrid(request.query, top_k=request.top_k, filter_by=filter_by)
            return self._response(request, results, filter_by)

        results = self.backend.search(request.query, top_k=request.top_k, filter_by=filter_by)
        return self._response(request, results, filter_by)

    def _response(
        self,
        request: RetrievalRequest,
        results: list,
        filter_by: dict[str, Any] | None,
        metadata: dict[str, Any] | None = None,
    ) -> RetrievalResponse:
        return RetrievalResponse(
            results=results,
            provider=self.provider,
            retrieval_mode=request.retrieval_mode,
            security_mode=request.security_mode,
            filter_applied=bool(filter_by),
            acl_applied=bool(request.acl_filter),
            metadata=metadata or {},
        )
