from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from core.interfaces.rag_retriever import RetrievalResponse
from core.rag import RAGRetrievalMode, RAGSecurityMode
from serving.rag.pipeline import DEFAULT_RAG_QA_TEMPLATE, RAGPipeline
from storage.prompt_registry.registry import LocalPromptRegistry
from storage.vector_store.qdrant_store import SearchResult


@dataclass
class FakeRetriever:
    results: list[SearchResult]

    def retrieve(self, request):
        return RetrievalResponse(
            results=self.results,
            provider="test",
            retrieval_mode=RAGRetrievalMode.VECTOR,
            security_mode=RAGSecurityMode.NONE,
            filter_applied=False,
            acl_applied=False,
        )


class FakeVectorStore:
    pass


def test_default_rag_prompt_is_advisor_specific_and_refuses_missing_evidence(tmp_path):
    registry = LocalPromptRegistry(str(tmp_path / "prompts.json"))
    pipeline = RAGPipeline(
        vector_store=FakeVectorStore(),
        prompt_registry=registry,
        retriever=FakeRetriever(results=[]),
    )

    with patch("serving.rag.pipeline.litellm.completion") as completion:
        completion.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="I don't know based on the provided sources."))],
            usage={"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        )
        pipeline.query("Can I certify this beam as safe?")

    prompt = registry.get("rag_qa")
    assert prompt.template == DEFAULT_RAG_QA_TEMPLATE
    assert "Build Stage Inspector Advisor" in prompt.template
    assert "I don't know based on the provided sources" in prompt.template
    assert "qualified professional" in prompt.template


def test_context_includes_citation_metadata_for_advisor_prompt(tmp_path):
    result = SearchResult(
        chunk_id="chunk-1",
        document_id="doc-1",
        content="External waterproofing must follow the cited provision.",
        score=0.91,
        metadata={
            "source_title": "NCC 2022 Volume Two",
            "document_type": "regulation",
            "clause": "10.2.1",
            "inspection_stage": "waterproofing",
        },
    )
    pipeline = RAGPipeline(
        vector_store=FakeVectorStore(),
        prompt_registry=LocalPromptRegistry(str(tmp_path / "prompts.json")),
        retriever=FakeRetriever(results=[result]),
    )

    context = pipeline._build_context([result])

    assert "title=NCC 2022 Volume Two" in context
    assert "type=regulation" in context
    assert "locator=10.2.1" in context
    assert "stage=waterproofing" in context
