"""
data_ingestion/chunking/chunker.py
Pluggable chunking strategies for preparing documents for embedding.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator

import tiktoken


@dataclass
class Chunk:
    id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


class ChunkStrategy(str, Enum):
    FIXED_TOKENS = "fixed_tokens"       # Fixed token window with overlap
    SENTENCE = "sentence"               # Split on sentence boundaries
    RECURSIVE = "recursive"             # LangChain-style recursive character splitting
    SEMANTIC = "semantic"               # Embed-and-cluster (expensive, high quality)


class _WhitespaceEncoding:
    """
    Offline fallback for framework tests and air-gapped development.

    It is not a production token counter, but it preserves deterministic
    chunk/overlap behavior when tiktoken cannot load its encoding cache.
    """

    @staticmethod
    def encode(text: str) -> list[str]:
        return text.split()

    @staticmethod
    def decode(tokens: list[str]) -> str:
        return " ".join(tokens)


class TokenChunker:
    """Fixed-size token chunking with configurable overlap (default strategy)."""

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
        encoding_name: str = "cl100k_base",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        try:
            self.enc = tiktoken.get_encoding(encoding_name)
        except Exception:
            self.enc = _WhitespaceEncoding()

    def chunk(self, document_id: str, text: str, metadata: dict | None = None) -> list[Chunk]:
        tokens = self.enc.encode(text)
        chunks: list[Chunk] = []
        start = 0
        idx = 0
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            content = self.enc.decode(chunk_tokens)
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                content=content,
                chunk_index=idx,
                metadata={**(metadata or {}), "token_start": start, "token_end": end},
            ))
            start += self.chunk_size - self.chunk_overlap
            idx += 1
        return chunks


class SentenceChunker:
    """Splits on sentence boundaries, grouping up to max_sentences per chunk."""

    def __init__(self, max_sentences: int = 8, overlap_sentences: int = 1):
        self.max_sentences = max_sentences
        self.overlap_sentences = overlap_sentences

    def _split_sentences(self, text: str) -> list[str]:
        import re
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

    def chunk(self, document_id: str, text: str, metadata: dict | None = None) -> list[Chunk]:
        sentences = self._split_sentences(text)
        chunks: list[Chunk] = []
        start = 0
        idx = 0
        while start < len(sentences):
            end = min(start + self.max_sentences, len(sentences))
            content = " ".join(sentences[start:end])
            chunks.append(Chunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                content=content,
                chunk_index=idx,
                metadata={**(metadata or {}), "sentence_start": start, "sentence_end": end},
            ))
            start += self.max_sentences - self.overlap_sentences
            idx += 1
        return chunks


def get_chunker(strategy: ChunkStrategy = ChunkStrategy.FIXED_TOKENS, **kwargs):
    """Factory returning the requested chunker."""
    if strategy == ChunkStrategy.FIXED_TOKENS:
        return TokenChunker(**kwargs)
    if strategy == ChunkStrategy.SENTENCE:
        return SentenceChunker(**kwargs)
    raise NotImplementedError(f"Strategy {strategy} not yet implemented — contribute it!")
