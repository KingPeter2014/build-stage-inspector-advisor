from data_ingestion.sources.base import RawDocument
from scripts import run_ingestion as ingestion_script


class FakeConnector:
    def fetch(self):
        yield RawDocument(
            id="doc_stable",
            content=(
                "This is a sufficiently long document for ingestion. "
                "It has enough text to pass cleaning and create at least one chunk. "
                "The content is stable for idempotence testing."
            ),
            source="data/raw_docs/NCC 2022/example.md",
            source_type="unstructured",
            metadata={"filename": "NCC 2022 Volume One.md"},
        )


class FakeVectorStore:
    def __init__(self):
        self.calls = []
        self.chunks = []

    def delete_by_document(self, document_id):
        self.calls.append(("delete", document_id))

    def upsert_chunks(self, chunks):
        self.calls.append(("upsert", [chunk.id for chunk in chunks]))
        self.chunks.extend(chunks)


def test_ingestion_deletes_existing_document_before_upserting_hashed_chunks(monkeypatch):
    store = FakeVectorStore()
    monkeypatch.setattr(
        ingestion_script,
        "_build_source_and_store",
        lambda provider, source_dir, env, *args: (FakeConnector(), store),
    )

    stats = ingestion_script.run_ingestion(
        provider="open_source",
        source_dir="data/raw_docs/NCC 2022",
        env="development",
    )

    assert stats["errors"] == 0
    assert store.calls[0] == ("delete", "doc_stable")
    assert store.calls[1][0] == "upsert"
    assert store.chunks
    for chunk in store.chunks:
        assert chunk.document_id == "doc_stable"
        assert chunk.metadata["document_id"] == "doc_stable"
        assert len(chunk.metadata["document_hash"]) == 64
        assert chunk.metadata["chunk_id"] == chunk.id
        assert len(chunk.metadata["chunk_hash"]) == 64


def test_ingestion_chunk_ids_repeat_for_same_document(monkeypatch):
    first_store = FakeVectorStore()
    second_store = FakeVectorStore()
    stores = iter([first_store, second_store])
    monkeypatch.setattr(
        ingestion_script,
        "_build_source_and_store",
        lambda provider, source_dir, env, *args: (FakeConnector(), next(stores)),
    )

    ingestion_script.run_ingestion("open_source", "data/raw_docs/NCC 2022")
    ingestion_script.run_ingestion("open_source", "data/raw_docs/NCC 2022")

    assert [chunk.id for chunk in first_store.chunks] == [
        chunk.id for chunk in second_store.chunks
    ]
