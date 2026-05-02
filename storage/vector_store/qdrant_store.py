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

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection_name not in existing:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
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
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )
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
