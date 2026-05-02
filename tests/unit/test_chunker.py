"""
tests/unit/test_chunker.py
Unit tests for the chunking strategies.
"""
import pytest
from data_ingestion.chunking.chunker import TokenChunker, SentenceChunker, ChunkStrategy, get_chunker

SAMPLE_TEXT = (
    "Large language models are transforming how we build software. "
    "They can understand and generate natural language at scale. "
    "However, deploying them reliably requires robust LLMOps practices. "
    "This includes data ingestion, evaluation, and continuous monitoring. "
    "Teams that invest in these foundations ship faster and with more confidence."
)


class TestTokenChunker:
    def test_basic_chunking(self):
        chunker = TokenChunker(chunk_size=32, chunk_overlap=8)
        chunks = chunker.chunk("doc-1", SAMPLE_TEXT)
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.document_id == "doc-1"
            assert len(chunk.content) > 0

    def test_chunk_ids_are_unique(self):
        chunker = TokenChunker(chunk_size=32, chunk_overlap=8)
        chunks = chunker.chunk("doc-1", SAMPLE_TEXT)
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids))

    def test_overlap_creates_more_chunks(self):
        no_overlap = TokenChunker(chunk_size=50, chunk_overlap=0)
        with_overlap = TokenChunker(chunk_size=50, chunk_overlap=25)
        assert len(with_overlap.chunk("doc", SAMPLE_TEXT)) >= len(no_overlap.chunk("doc", SAMPLE_TEXT))

    def test_metadata_is_preserved(self):
        chunker = TokenChunker(chunk_size=64, chunk_overlap=16)
        meta = {"source": "test_file.pdf", "page": 1}
        chunks = chunker.chunk("doc-2", SAMPLE_TEXT, metadata=meta)
        for chunk in chunks:
            assert chunk.metadata["source"] == "test_file.pdf"
            assert chunk.metadata["page"] == 1

    def test_short_text_produces_single_chunk(self):
        chunker = TokenChunker(chunk_size=512, chunk_overlap=64)
        chunks = chunker.chunk("doc-3", "Short text.")
        assert len(chunks) == 1


class TestSentenceChunker:
    def test_sentence_chunking(self):
        chunker = SentenceChunker(max_sentences=2, overlap_sentences=0)
        chunks = chunker.chunk("doc-4", SAMPLE_TEXT)
        assert len(chunks) >= 2

    def test_chunk_index_increments(self):
        chunker = SentenceChunker(max_sentences=2, overlap_sentences=0)
        chunks = chunker.chunk("doc-5", SAMPLE_TEXT)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i


class TestGetChunker:
    def test_factory_returns_token_chunker(self):
        chunker = get_chunker(ChunkStrategy.FIXED_TOKENS, chunk_size=128)
        assert isinstance(chunker, TokenChunker)

    def test_factory_returns_sentence_chunker(self):
        chunker = get_chunker(ChunkStrategy.SENTENCE)
        assert isinstance(chunker, SentenceChunker)

    def test_unknown_strategy_raises(self):
        with pytest.raises(NotImplementedError):
            get_chunker(ChunkStrategy.SEMANTIC)
