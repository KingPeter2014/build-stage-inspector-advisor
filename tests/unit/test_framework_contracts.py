import pytest

from core.framework import FrameworkMode, decide_stub, get_framework_mode, require_env_vars
from core.rag import (
    RAG_CAPABILITY_MATRIX,
    RAGOptions,
    RAGRetrievalMode,
    RAGSecurityMode,
    build_acl_filter,
    merge_retrieval_filters,
)
from serving.rag.provider_registry import build_provider_rag_retriever
from serving.rag.retriever import GenericRAGRetriever


def test_reference_mode_allows_explicit_stubs(monkeypatch):
    monkeypatch.setenv("APP_COMPLEXITY", "reference")
    assert get_framework_mode() is FrameworkMode.REFERENCE

    decision = decide_stub("rag eval")
    assert decision.allowed is True
    assert "reference mode" in decision.reason


def test_production_mode_blocks_stubs(monkeypatch):
    monkeypatch.setenv("APP_COMPLEXITY", "starter-production")
    decision = decide_stub("rag eval")
    assert decision.allowed is False
    assert "starter-production" in decision.reason


def test_require_env_vars_reports_missing(monkeypatch):
    monkeypatch.delenv("REQUIRED_FOR_TEST", raising=False)
    with pytest.raises(RuntimeError, match="REQUIRED_FOR_TEST"):
        require_env_vars(["REQUIRED_FOR_TEST"], component="unit-test")


def test_rag_options_require_graph_when_graph_mode_selected():
    options = RAGOptions(
        retrieval_mode=RAGRetrievalMode.HYBRID_GRAPH,
        security_mode=RAGSecurityMode.METADATA_FILTERING,
        graph_enabled=False,
    )
    with pytest.raises(ValueError, match="GRAPH_ENABLED"):
        options.validate()


def test_acl_filter_builder_and_merge():
    acl = build_acl_filter(user_id="u1", groups=["g1", "g2"], tenant_id="t1")
    merged = merge_retrieval_filters({"source": "policy"}, acl)
    assert merged["source"] == "policy"
    assert merged["acl_user_ids"] == "u1"
    assert merged["acl_group_ids"] == ["g1", "g2"]
    assert merged["tenant_id"] == "t1"


def test_rag_provider_matrix_covers_all_supported_providers():
    assert set(RAG_CAPABILITY_MATRIX) == {"open_source"}
    assert "qdrant" in RAG_CAPABILITY_MATRIX["open_source"].vector.lower()
    assert "acl" in RAG_CAPABILITY_MATRIX["open_source"].acl_filtering.lower()


def test_rag_provider_registry_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unknown RAG provider"):
        build_provider_rag_retriever("unknown")


def test_generic_retriever_dispatches_hybrid_and_acl_filter():
    class HybridBackend:
        def __init__(self):
            self.called = None

        def search(self, query, top_k=5, filter_by=None):
            self.called = ("search", filter_by)
            return []

        def search_hybrid(self, query, top_k=5, filter_by=None):
            self.called = ("search_hybrid", filter_by)
            return []

    backend = HybridBackend()
    retriever = GenericRAGRetriever("test", backend)
    from core.interfaces.rag_retriever import RetrievalRequest

    response = retriever.retrieve(RetrievalRequest(
        query="q",
        retrieval_mode=RAGRetrievalMode.HYBRID,
        security_mode=RAGSecurityMode.ACL_FILTERING,
        metadata_filter={"tenant_id": "t1"},
        acl_filter={"acl_group_ids": ["g1"]},
    ))

    assert backend.called == ("search_hybrid", {"tenant_id": "t1", "acl_group_ids": ["g1"]})
    assert response.provider == "test"
    assert response.acl_applied is True


def test_generic_retriever_dispatches_graph_when_backend_supports_it():
    class GraphBackend:
        def __init__(self):
            self.called = None

        def search_graph_augmented(self, query, top_k=5, filter_by=None):
            self.called = ("search_graph_augmented", filter_by)
            return []

    backend = GraphBackend()
    retriever = GenericRAGRetriever("test", backend)
    from core.interfaces.rag_retriever import RetrievalRequest

    retriever.retrieve(RetrievalRequest(
        query="q",
        retrieval_mode=RAGRetrievalMode.GRAPH_AUGMENTED,
        security_mode=RAGSecurityMode.METADATA_FILTERING,
        metadata_filter={"tenant_id": "t1"},
    ))

    assert backend.called == ("search_graph_augmented", {"tenant_id": "t1"})
