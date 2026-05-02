from core.interfaces.rag_retriever import RetrievalRequest
from core.interfaces.vector_store import VectorSearchResult
from core.rag import RAGRetrievalMode, RAGSecurityMode
from serving.rag.retriever import GenericRAGRetriever


class ACLAwareBackend:
    def __init__(self):
        self.filter_seen = None

    def search(self, query, top_k=5, filter_by=None):
        self.filter_seen = filter_by
        allowed_groups = set((filter_by or {}).get("acl_group_ids", []))
        candidates = [
            VectorSearchResult(
                chunk_id="public",
                document_id="doc-public",
                content="public",
                score=1.0,
                metadata={"acl_group_ids": ["engineering"]},
            ),
            VectorSearchResult(
                chunk_id="private",
                document_id="doc-private",
                content="private",
                score=0.9,
                metadata={"acl_group_ids": ["finance"]},
            ),
        ]
        return [
            item for item in candidates
            if allowed_groups.intersection(item.metadata.get("acl_group_ids", []))
        ][:top_k]


def test_acl_filter_prevents_unauthorized_chunks_from_retriever_results():
    backend = ACLAwareBackend()
    retriever = GenericRAGRetriever("test", backend)

    response = retriever.retrieve(RetrievalRequest(
        query="policy",
        retrieval_mode=RAGRetrievalMode.VECTOR,
        security_mode=RAGSecurityMode.ACL_FILTERING,
        acl_filter={"acl_group_ids": ["engineering"]},
    ))

    assert response.acl_applied is True
    assert backend.filter_seen == {"acl_group_ids": ["engineering"]}
    assert [result.document_id for result in response.results] == ["doc-public"]


def test_metadata_and_acl_filters_are_both_sent_to_backend():
    backend = ACLAwareBackend()
    retriever = GenericRAGRetriever("test", backend)

    retriever.retrieve(RetrievalRequest(
        query="policy",
        retrieval_mode=RAGRetrievalMode.VECTOR,
        security_mode=RAGSecurityMode.POLICY_ENFORCED_ACL,
        metadata_filter={"tenant_id": "tenant-a"},
        acl_filter={"acl_group_ids": ["engineering"]},
    ))

    assert backend.filter_seen == {
        "tenant_id": "tenant-a",
        "acl_group_ids": ["engineering"],
    }
