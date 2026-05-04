"""
Stable document and chunk identities for idempotent indexing.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path


def normalize_source_uri(source: str) -> str:
    source = source.strip()
    if "://" in source:
        return source
    try:
        return str(Path(source).expanduser().resolve()).replace("\\", "/")
    except OSError:
        return source.replace("\\", "/")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_document_id(source: str) -> str:
    source_hash = sha256_text(normalize_source_uri(source))
    return f"doc_{source_hash[:32]}"


def stable_chunk_id(document_id: str, chunk_index: int, chunk_hash: str) -> str:
    """
    Return a deterministic UUID string accepted by Qdrant point IDs.

    The chunk hash is included so changed content gets fresh point IDs, while
    delete-by-document removes stale chunks before re-indexing.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{document_id}:{chunk_index}:{chunk_hash}"))
