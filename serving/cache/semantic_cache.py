"""
serving/cache/semantic_cache.py
Two-level LLM response cache:
  Level 1 — exact SHA-256 key match backed by Redis (or in-memory dict) with TTL.
  Level 2 — semantic similarity fallback using sentence-transformers embeddings;
             returns a cached response when cosine similarity >= threshold.

Usage:
    cache = SemanticCache(redis_url="redis://localhost:6379", ttl_seconds=3600)
    hit = cache.get(prompt)
    if hit is None:
        response = call_llm(prompt)
        cache.set(prompt, response)
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class _CacheEntry:
    response: str
    created_at: float


class SemanticCache:
    """
    Two-level cache for LLM responses.

    Parameters
    ----------
    similarity_threshold:
        Minimum cosine similarity [0, 1] to accept a semantic cache hit.
        0.92 works well for paraphrases; lower it for broader matching.
    ttl_seconds:
        Time-to-live for each entry. Entries older than this are treated as
        misses regardless of similarity.
    redis_url:
        Optional Redis connection string. Falls back to in-process dict when
        None or when the redis package is not installed.
    embed_model:
        sentence-transformers model name for semantic matching.
    """

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        ttl_seconds: int = 3600,
        redis_url: Optional[str] = None,
        embed_model: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.threshold = similarity_threshold
        self.ttl = ttl_seconds
        self._embed_model_name = embed_model
        self._encoder = None  # lazy-loaded

        # In-memory fallback store  {hex_key -> _CacheEntry}
        self._local: dict[str, _CacheEntry] = {}
        # Embedding index: list of (unit-normalised embedding, hex_key)
        self._index: list[tuple[np.ndarray, str]] = []

        # Redis store (optional)
        self._redis = None
        if redis_url:
            try:
                import redis as redis_lib
                self._redis = redis_lib.from_url(redis_url, decode_responses=True)
                self._redis.ping()
            except Exception:
                self._redis = None

    # ── Private helpers ────────────────────────────────────────────────────────

    def _encoder_(self):
        if self._encoder is None:
            from sentence_transformers import SentenceTransformer
            self._encoder = SentenceTransformer(self._embed_model_name)
        return self._encoder

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _read(self, key: str) -> Optional[_CacheEntry]:
        """Read from Redis or local dict; return None on miss or expiry."""
        if self._redis:
            raw = self._redis.get(f"semcache:{key}")
            if raw:
                d = json.loads(raw)
                return _CacheEntry(**d)
            return None
        entry = self._local.get(key)
        if entry and (time.time() - entry.created_at) < self.ttl:
            return entry
        return None

    def _write(self, key: str, entry: _CacheEntry) -> None:
        if self._redis:
            self._redis.setex(
                f"semcache:{key}",
                self.ttl,
                json.dumps({"response": entry.response, "created_at": entry.created_at}),
            )
        else:
            self._local[key] = entry

    def _embed(self, text: str) -> np.ndarray:
        return self._encoder_().encode(text, normalize_embeddings=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def get(self, prompt: str) -> Optional[str]:
        """Return a cached response or None on cache miss."""
        # Level 1: exact match
        key = self._key(prompt)
        entry = self._read(key)
        if entry:
            return entry.response

        # Level 2: semantic similarity
        query_emb = self._embed(prompt)
        best_score, best_key = 0.0, None
        for emb, k in self._index:
            score = float(np.dot(query_emb, emb))
            if score > best_score:
                best_score, best_key = score, k

        if best_score >= self.threshold and best_key:
            entry = self._read(best_key)
            if entry:
                return entry.response

        return None

    def set(self, prompt: str, response: str) -> None:
        """Store a prompt → response pair in both levels."""
        key = self._key(prompt)
        entry = _CacheEntry(response=response, created_at=time.time())
        self._write(key, entry)
        emb = self._embed(prompt)
        # Replace existing entry in index or append
        for i, (_, k) in enumerate(self._index):
            if k == key:
                self._index[i] = (emb, key)
                return
        self._index.append((emb, key))

    def invalidate(self, prompt: str) -> None:
        """Remove a specific entry from the cache."""
        key = self._key(prompt)
        if self._redis:
            self._redis.delete(f"semcache:{key}")
        else:
            self._local.pop(key, None)
        self._index = [(e, k) for e, k in self._index if k != key]

    def clear(self) -> None:
        """Flush the entire cache (dev/testing use)."""
        if self._redis:
            for k in self._redis.scan_iter("semcache:*"):
                self._redis.delete(k)
        self._local.clear()
        self._index.clear()

    @property
    def size(self) -> int:
        return len(self._index)
