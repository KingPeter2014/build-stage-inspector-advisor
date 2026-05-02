"""
providers/azure/storage/blob_lake.py
Azure Blob Storage / ADLS Gen2 data lake — AbstractDataLake implementation.
"""
from __future__ import annotations

import json
from io import BytesIO

from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

from core.interfaces.data_lake import AbstractDataLake, LakeObject
from providers.azure.config.settings import get_azure_settings


class AzureBlobDataLake(AbstractDataLake):
    """
    AbstractDataLake backed by Azure Blob Storage (or ADLS Gen2 hierarchical namespace).
    Object keys follow the convention: {partition}/{key}
    """

    def __init__(self, container: str | None = None) -> None:
        s = get_azure_settings()
        self._container = container or s.azure_storage_container

        if s.azure_storage_connection_string:
            self._service = BlobServiceClient.from_connection_string(
                s.azure_storage_connection_string
            )
        else:
            self._service = BlobServiceClient(
                account_url=f"https://{s.azure_storage_account_name}.blob.core.windows.net",
                credential=DefaultAzureCredential(),
            )
        self._container_client = self._service.get_container_client(self._container)
        if not self._container_client.exists():
            self._container_client.create_container()

    def _full_key(self, key: str, partition: str = "") -> str:
        return f"{partition}/{key}" if partition else key

    def upload_json(self, data: dict | list, key: str, partition: str = "raw") -> str:
        full_key = self._full_key(key, partition)
        payload = json.dumps(data, default=str).encode()
        self._container_client.upload_blob(
            name=full_key,
            data=payload,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/json"),
        )
        return f"https://{self._service.account_name}.blob.core.windows.net/{self._container}/{full_key}"

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        self._container_client.upload_blob(
            name=key,
            data=data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return f"https://{self._service.account_name}.blob.core.windows.net/{self._container}/{key}"

    def download_json(self, key: str) -> dict | list:
        blob = self._container_client.download_blob(key)
        return json.loads(blob.readall())

    def download_bytes(self, key: str) -> bytes:
        return self._container_client.download_blob(key).readall()

    def list_partition(self, partition: str, prefix: str = "") -> list[LakeObject]:
        full_prefix = self._full_key(prefix, partition) if prefix else f"{partition}/"
        return [
            LakeObject(
                key=b.name,
                size_bytes=b.size or 0,
                last_modified=b.last_modified.isoformat() if b.last_modified else "",
                partition=partition,
            )
            for b in self._container_client.list_blobs(name_starts_with=full_prefix)
        ]

    def delete(self, key: str) -> None:
        self._container_client.delete_blob(key, delete_snapshots="include")
