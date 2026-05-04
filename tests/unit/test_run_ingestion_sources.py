import sys
from types import ModuleType

from scripts.run_ingestion import _build_source_and_store


class FakeSettings:
    qdrant_collection_name = "test_collection"
    qdrant_url = "http://qdrant"
    qdrant_api_key = ""


def test_build_source_and_store_uses_web_manifest(monkeypatch):
    built = {}

    class FakeWebConnector:
        @classmethod
        def from_manifest(cls, manifest):
            built["manifest"] = manifest
            return "web-connector"

    class FakeVectorStore:
        def __init__(self, **kwargs):
            built["vector_store"] = kwargs

    settings_module = ModuleType("config.settings")
    settings_module.get_settings = lambda: FakeSettings()
    web_module = ModuleType("data_ingestion.sources.web_connector")
    web_module.WebPageConnector = FakeWebConnector
    qdrant_module = ModuleType("storage.vector_store.qdrant_store")
    qdrant_module.QdrantVectorStore = FakeVectorStore

    monkeypatch.setitem(sys.modules, "config.settings", settings_module)
    monkeypatch.setitem(sys.modules, "data_ingestion.sources.web_connector", web_module)
    monkeypatch.setitem(sys.modules, "storage.vector_store.qdrant_store", qdrant_module)

    connector, _ = _build_source_and_store(
        "open_source",
        "data/raw_docs",
        "development",
        "web",
        "manifest.json",
    )

    assert connector == "web-connector"
    assert built["manifest"] == "manifest.json"
    assert built["vector_store"]["collection_name"] == "test_collection"
