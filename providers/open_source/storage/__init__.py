"""
providers/open_source/storage
Wires OSS storage backends to core interfaces.
"""
from storage.vector_store.qdrant_store import QdrantVectorStore  # noqa: F401
from storage.data_lake.s3_store import S3DataLake  # noqa: F401
from storage.feature_store.feast_store import FeastFeatureStore  # noqa: F401
from storage.prompt_registry.registry import LocalPromptRegistry, LangfusePromptRegistry  # noqa: F401

from core.interfaces.vector_store import AbstractVectorStore, VectorSearchResult
from core.interfaces.data_lake import AbstractDataLake, LakeObject
from data_ingestion.chunking.chunker import Chunk
from typing import Any
import json
import io


class OSSVectorStore(AbstractVectorStore):
    """AbstractVectorStore backed by Qdrant."""

    def __init__(self, **kwargs):
        self._store = QdrantVectorStore(**kwargs)

    def upsert_chunks(self, chunks: list) -> None:
        self._store.upsert_chunks(chunks)

    def search(self, query: str, top_k: int = 5, filter_by: dict | None = None) -> list[VectorSearchResult]:
        results = self._store.search(query, top_k=top_k, filter_by=filter_by)
        return [
            VectorSearchResult(
                chunk_id=r.chunk_id,
                document_id=r.document_id,
                content=r.content,
                score=r.score,
                metadata=r.metadata,
            )
            for r in results
        ]

    def delete_by_document(self, document_id: str) -> None:
        self._store.delete_by_document(document_id)


class OSSS3DataLake(AbstractDataLake):
    """AbstractDataLake backed by S3/MinIO."""

    def __init__(self, bucket: str, **kwargs):
        self._lake = S3DataLake(bucket_name=bucket, **kwargs)
        self._bucket = bucket

    def upload_json(self, data: dict | list, key: str, partition: str = "raw") -> str:
        return self._lake.upload_json(data, key, partition=partition)

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        import boto3
        self._lake._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return f"s3://{self._bucket}/{key}"

    def download_json(self, key: str) -> dict | list:
        return self._lake.download_json(key)

    def download_bytes(self, key: str) -> bytes:
        import boto3
        obj = self._lake._s3.get_object(Bucket=self._bucket, Key=key)
        return obj["Body"].read()

    def list_partition(self, partition: str, prefix: str = "") -> list[LakeObject]:
        objects = self._lake.list_partition(partition, prefix=prefix)
        return [
            LakeObject(key=o.key, size_bytes=o.size_bytes,
                       last_modified=str(o.last_modified), partition=partition)
            for o in objects
        ]

    def delete(self, key: str) -> None:
        self._lake._s3.delete_object(Bucket=self._bucket, Key=key)
