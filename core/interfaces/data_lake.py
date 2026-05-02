"""
core/interfaces/data_lake.py
Abstract data lake contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LakeObject:
    key: str
    size_bytes: int
    last_modified: str
    partition: str


class AbstractDataLake(ABC):
    """
    Uniform interface for object-store data lakes.
    Implementations: S3/MinIO (OSS), Azure Blob/ADLS Gen2, Amazon S3, Google Cloud Storage.
    """

    @abstractmethod
    def upload_json(self, data: dict | list, key: str, partition: str = "raw") -> str:
        """Serialise to JSON and upload; return the full object URI."""

    @abstractmethod
    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
        """Upload raw bytes; return the full object URI."""

    @abstractmethod
    def download_json(self, key: str) -> dict | list:
        """Download and deserialise a JSON object."""

    @abstractmethod
    def download_bytes(self, key: str) -> bytes:
        """Download raw bytes."""

    @abstractmethod
    def list_partition(self, partition: str, prefix: str = "") -> list[LakeObject]:
        """List objects in a logical partition."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a single object."""
