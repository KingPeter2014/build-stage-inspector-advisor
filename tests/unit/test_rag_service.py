from dataclasses import dataclass

from core.schemas.rag import RAGQueryRequest, RAGQueryResponse, RAGSource
from serving.rag.service import (
    build_filter,
    format_rag_response,
    query_knowledge_base_api,
    search_knowledge_base_text,
)


@dataclass
class FakeSource:
    document_id: str
    metadata: dict


@dataclass
class FakeResponse:
    answer: str
    sources: list[FakeSource]


class FakePipeline:
    def __init__(self):
        self.called_with = None

    def query(self, question, filter_by=None, acl_filter=None):
        self.called_with = (question, filter_by, acl_filter)
        return FakeResponse(
            answer="Use the cited NCC clause.",
            sources=[
                FakeSource("doc-1", {"source_title": "NCC 2022 Volume One", "volume": "Volume One"}),
                FakeSource("doc-2", {"filename": "domestic-building-contract.md", "clause": "Clause 7"}),
            ],
        )


def test_build_filter_keeps_optional_document_type_and_tenant():
    assert build_filter(document_type="contract", tenant_id="t1") == {
        "document_type": "contract",
        "tenant_id": "t1",
    }
    assert build_filter() == {}


def test_format_rag_response_adds_compact_sources():
    text = format_rag_response(FakeResponse(
        answer="Answer",
        sources=[FakeSource("doc", {"source_title": "Policy", "section": "S1"})],
    ))

    assert text == "Answer\n\nSources: Policy S1"


def test_agent_rag_tool_uses_pipeline_with_metadata_filter():
    pipeline = FakePipeline()

    text = search_knowledge_base_text(
        query="What is required?",
        document_type="regulation",
        tenant_id="tenant-a",
        pipeline=pipeline,
    )

    assert pipeline.called_with == (
        "What is required?",
        {"document_type": "regulation", "tenant_id": "tenant-a"},
        None,
    )
    assert "Use the cited NCC clause." in text
    assert "NCC 2022 Volume One Volume One" in text


def test_rag_api_client_posts_to_rest_endpoint(monkeypatch):
    calls = []

    class FakeHTTPResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return RAGQueryResponse(
                answer="REST answer",
                sources=[RAGSource(document_id="doc-1")],
                model="gpt-4o",
            ).model_dump()

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return FakeHTTPResponse()

    monkeypatch.setattr("serving.rag.service.httpx.post", fake_post)

    response = query_knowledge_base_api(
        RAGQueryRequest(question="q", filter_by={"document_type": "policy"}),
        api_url="http://rag.internal/v1/rag/query",
        timeout_seconds=3.0,
    )

    assert response.answer == "REST answer"
    assert calls == [(
        "http://rag.internal/v1/rag/query",
        {
            "question": "q",
            "filter_by": {"document_type": "policy"},
            "acl_filter": {},
            "top_k": 5,
            "session_id": "",
        },
        3.0,
    )]
