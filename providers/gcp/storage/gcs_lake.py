"""
providers/gcp/storage/gcs_lake.py
Google Cloud Storage data lake — AbstractDataLake implementation.
"""
from __future__ import annotations

import json
from io import BytesIO

from google.cloud import storage

from core.interfaces.data_lake import AbstractDataLake, LakeObject
from providers.gcp.config.settings import get_gcp_settings


class GCSDataLake(AbstractDataLake):
    """AbstractDataLake backed by Google Cloud Storage. Object keys: {partition}/{key}."""

    def __init__(self, bucket: str | None = None) -> None:
        s = get_gcp_settings()
        self._bucket_name = bucket or s.gcs_bucket
        self._client = storage.Client(project=s.gcp_project_id)
        self._bucket = self._client.bucket(self._bucket_name)
        if not self._bucket.exists():
            self._client.create_bucket(self._bucket_name, location=s.gcp_region)

    def _full_key(self, key: str, partition: str = "") -> str:
        return f"{partition}/{key}" if partition else key

    def upload_json(self, data: dict | list, key: str, partition: str = "raw") -> str:
        full_key = self._full_key(key, partition)
        blob = self._bucket.blob(full_key)
        blob.upload_from_string(json.dumps(data, default=str), content_type="application/json")
        return f"gs://{self._bucket_name}/{full_key}"

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        blob = self._bucket.blob(key)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self._bucket_name}/{key}"

    def download_json(self, key: str) -> dict | list:
        return json.loads(self._bucket.blob(key).download_as_text())

    def download_bytes(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def list_partition(self, partition: str, prefix: str = "") -> list[LakeObject]:
        full_prefix = self._full_key(prefix, partition) if prefix else f"{partition}/"
        return [
            LakeObject(
                key=blob.name,
                size_bytes=blob.size or 0,
                last_modified=blob.updated.isoformat() if blob.updated else "",
                partition=partition,
            )
            for blob in self._client.list_blobs(self._bucket_name, prefix=full_prefix)
        ]

    def delete(self, key: str) -> None:
        self._bucket.blob(key).delete()
