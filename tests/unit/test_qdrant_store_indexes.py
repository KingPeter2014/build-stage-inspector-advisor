from storage.vector_store.qdrant_store import QdrantVectorStore


class FakeCollection:
    payload_schema = {"tenant_id": object()}


class FakeClient:
    def __init__(self):
        self.created = []

    def get_collection(self, collection_name):
        assert collection_name == "buildstage_documents_development"
        return FakeCollection()

    def create_payload_index(self, **kwargs):
        self.created.append(kwargs)


def test_qdrant_store_creates_keyword_indexes_for_filtered_payload_fields():
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store.collection_name = "buildstage_documents_development"
    store.client = FakeClient()

    store._ensure_payload_indexes()

    created_fields = {call["field_name"] for call in store.client.created}
    assert "document_id" in created_fields
    assert "document_type" in created_fields
    assert "inspection_stage" in created_fields
    assert "acl_group_ids" in created_fields
    assert "tenant_id" not in created_fields
    assert all(call["field_schema"] == "keyword" for call in store.client.created)
    assert all(call["wait"] is True for call in store.client.created)


class FakeQueryResponse:
    def __init__(self, points):
        self.points = points


class FakeQueryClient:
    def __init__(self):
        self.called_with = None

    def query_points(self, **kwargs):
        self.called_with = kwargs
        return FakeQueryResponse([])


def test_qdrant_store_uses_query_points_when_search_api_is_unavailable():
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store.collection_name = "buildstage_documents_development"
    store.client = FakeQueryClient()

    results = store._search_points([0.1, 0.2], 3, None)

    assert results == []
    assert store.client.called_with == {
        "collection_name": "buildstage_documents_development",
        "query": [0.1, 0.2],
        "limit": 3,
        "query_filter": None,
        "with_payload": True,
    }
