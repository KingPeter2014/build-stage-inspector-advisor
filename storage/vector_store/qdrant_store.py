"""
storage/vector_store/qdrant_store.py
Qdrant-backed vector store with embedding generation and similarity search.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    PayloadSchemaType,
)
from sentence_transformers import SentenceTransformer

from data_ingestion.chunking.chunker import Chunk


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict[str, Any]


class QdrantVectorStore:
    KEYWORD_INDEX_FIELDS = (
        "document_id",
        "chunk_id",
        "document_type",
        "source_type",
        "source_uri",
        "source_title",
        "source_version",
        "document_family",
        "jurisdiction",
        "section",
        "clause",
        "volume",
        "building_class",
        "inspection_stage",
        "project_id",
        "contract_id",
        "tenant_id",
        "acl_user_ids",
        "acl_group_ids",
        "trust_level",
        "tags",
    )

    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: str | None = None,
        collection_name: str = "llmops_chunks",
        embedding_model: str = "all-MiniLM-L6-v2",
        vector_size: int = 384,
    ):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url, api_key=api_key or None)
        self.embedder = SentenceTransformer(embedding_model)
        self.vector_size = vector_size
        self._ensure_collection()
        self._ensure_payload_indexes()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )

    def _ensure_payload_indexes(self) -> None:
        """
        Qdrant Cloud requires payload indexes for fields used in filters.

        Ingestion deletes existing chunks by document_id before re-indexing, so
        document_id must be indexed before the first filtered delete. The other
        indexes cover the domain metadata and ACL filters used by RAG queries.
        """
        collection = self.client.get_collection(self.collection_name)
        existing_indexes = set((collection.payload_schema or {}).keys())
        for field_name in self.KEYWORD_INDEX_FIELDS:
            if field_name in existing_indexes:
                continue
            self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name=field_name,
                field_schema=PayloadSchemaType.KEYWORD,
                wait=True,
            )

    def upsert_chunks(self, chunks: list[Chunk]) -> None:
        texts = [c.content for c in chunks]
        vectors = self.embedder.encode(texts, show_progress_bar=False).tolist()
        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={
                    "document_id": chunk.document_id,
                    "chunk_id": chunk.id,
                    "content": chunk.content,
                    "chunk_index": chunk.chunk_index,
                    **chunk.metadata,
                },
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        self.client.upsert(collection_name=self.collection_name, points=points)

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter_by: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        query_vector = self.embedder.encode([query])[0].tolist()
        qdrant_filter = None
        if filter_by:
            qdrant_filter = Filter(must=self._build_conditions(filter_by))
        results = self._search_points(query_vector, top_k, qdrant_filter)
        return [
            SearchResult(
                chunk_id=str(r.id),
                document_id=r.payload.get("document_id", ""),
                content=r.payload.get("content", ""),
                score=r.score,
                metadata={k: v for k, v in r.payload.items() if k not in {"document_id", "content"}},
            )
            for r in results
        ]

    def _search_points(
        self,
        query_vector: list[float],
        top_k: int,
        qdrant_filter: Filter | None,
    ) -> list[Any]:
        if hasattr(self.client, "search"):
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
                with_payload=True,
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
        return list(getattr(response, "points", response))

    @staticmethod
    def _build_conditions(filter_by: dict[str, Any]) -> list[FieldCondition]:
        conditions = []
        for key, value in filter_by.items():
            if isinstance(value, (list, tuple, set)):
                conditions.append(FieldCondition(key=key, match=MatchAny(any=list(value))))
            else:
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
        return conditions

    def delete_by_document(self, document_id: str) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )
