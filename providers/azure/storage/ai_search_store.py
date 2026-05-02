"""
providers/azure/storage/ai_search_store.py
Azure AI Search vector store implementation of AbstractVectorStore.

Uses the azure-search-documents SDK with vector search (HNSW index).
Embeddings are generated with Azure OpenAI text-embedding-3-small
or a local sentence-transformers model as fallback.
"""
from __future__ import annotations

from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)
from azure.search.documents.models import VectorizedQuery

from core.interfaces.vector_store import AbstractVectorStore, VectorSearchResult
from providers.azure.config.settings import get_azure_settings


class AzureAISearchStore(AbstractVectorStore):
    """
    AbstractVectorStore backed by Azure AI Search with HNSW vector index.
    Supports hybrid search (keyword + vector) when use_hybrid=True.
    """

    VECTOR_DIM = 1536   # text-embedding-3-small output dimension

    def __init__(
        self,
        index_name: str | None = None,
        use_hybrid: bool = True,
    ) -> None:
        s = get_azure_settings()
        self._index_name = index_name or s.azure_search_index_name
        self._use_hybrid = use_hybrid
        credential = AzureKeyCredential(s.azure_search_api_key)

        self._index_client = SearchIndexClient(
            endpoint=s.azure_search_endpoint, credential=credential
        )
        self._search_client = SearchClient(
            endpoint=s.azure_search_endpoint,
            index_name=self._index_name,
            credential=credential,
        )
        self._embedder = self._build_embedder(s)
        self._ensure_index()

    @staticmethod
    def _escape_odata(value: Any) -> str:
        return str(value).replace("'", "''")

    @classmethod
    def _build_filter(cls, filter_by: dict[str, Any] | None) -> str | None:
        if not filter_by:
            return None

        clauses: list[str] = []
        for key, value in filter_by.items():
            if isinstance(value, (list, tuple, set)):
                values = [f"{key} eq '{cls._escape_odata(v)}'" for v in value]
                clauses.append("(" + " or ".join(values) + ")")
            else:
                clauses.append(f"{key} eq '{cls._escape_odata(value)}'")
        return " and ".join(clauses)

    # ── Embedding ──────────────────────────────────────────────────────────────

    @staticmethod
    def _build_embedder(s):
        """Use Azure OpenAI embeddings; fall back to sentence-transformers."""
        try:
            from openai import AzureOpenAI
            client = AzureOpenAI(
                azure_endpoint=s.azure_openai_endpoint,
                api_key=s.azure_openai_api_key,
                api_version=s.azure_openai_api_version,
            )

            def embed(texts: list[str]) -> list[list[float]]:
                resp = client.embeddings.create(
                    model="text-embedding-3-small", input=texts
                )
                return [d.embedding for d in resp.data]

            return embed
        except Exception:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")

            def embed_local(texts: list[str]) -> list[list[float]]:
                return model.encode(texts, normalize_embeddings=True).tolist()

            return embed_local

    # ── Index management ───────────────────────────────────────────────────────

    def _ensure_index(self) -> None:
        existing = [idx.name for idx in self._index_client.list_indexes()]
        if self._index_name in existing:
            return

        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SimpleField(name="document_id", type=SearchFieldDataType.String, filterable=True),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchField(
                name="embedding",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=self.VECTOR_DIM,
                vector_search_profile_name="hnsw-profile",
            ),
        ]
        vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
            profiles=[VectorSearchProfile(name="hnsw-profile", algorithm_configuration_name="hnsw-config")],
        )
        self._index_client.create_index(
            SearchIndex(name=self._index_name, fields=fields, vector_search=vector_search)
        )

    # ── AbstractVectorStore ────────────────────────────────────────────────────

    def upsert_chunks(self, chunks: list) -> None:
        texts = [c.content for c in chunks]
        embeddings = self._embedder(texts)
        documents = [
            {
                "id": c.id,
                "document_id": c.document_id,
                "content": c.content,
                "embedding": emb,
            }
            for c, emb in zip(chunks, embeddings)
        ]
        self._search_client.upload_documents(documents)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_by: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        query_emb = self._embedder([query])[0]
        vector_query = VectorizedQuery(
            vector=query_emb, k_nearest_neighbors=top_k, fields="embedding"
        )
        results = self._search_client.search(
            search_text=query if self._use_hybrid else None,
            vector_queries=[vector_query],
            filter=self._build_filter(filter_by),
            top=top_k,
        )
        return [
            VectorSearchResult(
                chunk_id=r["id"],
                document_id=r.get("document_id", ""),
                content=r.get("content", ""),
                score=r["@search.score"],
            )
            for r in results
        ]

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        filter_by: dict[str, Any] | None = None,
    ) -> list[VectorSearchResult]:
        """Run Azure AI Search hybrid keyword + vector retrieval."""
        original = self._use_hybrid
        self._use_hybrid = True
        try:
            return self.search(query, top_k=top_k, filter_by=filter_by)
        finally:
            self._use_hybrid = original

    def delete_by_document(self, document_id: str) -> None:
        results = self._search_client.search(
            search_text="*",
            filter=f"document_id eq '{document_id}'",
            select=["id"],
        )
        ids = [{"id": r["id"]} for r in results]
        if ids:
            self._search_client.delete_documents(ids)
