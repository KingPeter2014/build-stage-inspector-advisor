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


def test_azure_settings_accept_terraform_env_aliases(monkeypatch):
    from providers.azure.config.settings import get_azure_settings, reset_azure_settings

    reset_azure_settings()
    monkeypatch.setenv("AZURE_AI_SEARCH_ENDPOINT", "https://search.example.net")
    monkeypatch.setenv("AZURE_AI_SEARCH_API_KEY", "search-key")
    monkeypatch.setenv("REDIS_URL", "rediss://redis.example.net:6380")

    settings = get_azure_settings()
    assert settings.azure_search_endpoint == "https://search.example.net"
    assert settings.azure_search_api_key == "search-key"
    assert settings.azure_redis_url == "rediss://redis.example.net:6380"
    reset_azure_settings()


def test_aws_settings_accept_runtime_env_aliases(monkeypatch):
    from providers.aws.config.settings import get_aws_settings, reset_aws_settings

    reset_aws_settings()
    monkeypatch.setenv("S3_BUCKET_NAME", "terraform-bucket")
    monkeypatch.setenv("REDIS_URL", "redis://redis.example.net:6379")

    settings = get_aws_settings()
    assert settings.s3_bucket == "terraform-bucket"
    assert settings.aws_redis_url == "redis://redis.example.net:6379"
    reset_aws_settings()


def test_gcp_settings_accept_runtime_env_aliases(monkeypatch):
    from providers.gcp.config.settings import get_gcp_settings, reset_gcp_settings

    reset_gcp_settings()
    monkeypatch.setenv("VECTOR_SEARCH_INDEX_ENDPOINT", "projects/p/locations/r/indexEndpoints/1")
    monkeypatch.setenv("VECTOR_SEARCH_DEPLOYED_INDEX_ID", "llmops_idx")
    monkeypatch.setenv("GCS_BUCKET_NAME", "terraform-gcs-bucket")
    monkeypatch.setenv("REDIS_HOST", "10.0.0.3")
    monkeypatch.setenv("REDIS_PORT", "6379")

    settings = get_gcp_settings()
    assert settings.vertex_index_endpoint_id == "projects/p/locations/r/indexEndpoints/1"
    assert settings.vertex_deployed_index_id == "llmops_idx"
    assert settings.gcs_bucket == "terraform-gcs-bucket"
    assert settings.gcp_redis_url == "redis://10.0.0.3:6379"
    reset_gcp_settings()


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
    assert set(RAG_CAPABILITY_MATRIX) == {"open_source", "azure", "aws", "gcp"}
    assert "hybrid" in RAG_CAPABILITY_MATRIX["azure"].hybrid.lower()
    assert "acl" in RAG_CAPABILITY_MATRIX["aws"].acl_filtering.lower()


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
