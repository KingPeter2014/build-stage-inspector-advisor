import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient

from core.interfaces.agent_runner import AgentOutput
from core.schemas.rag import RAGQueryResponse, RAGSource
from serving.gateway.app import app, get_agent_runner


class FakeAgentRunner:
    def run(self, input):
        return AgentOutput(
            response=f"handled: {input.message}",
            session_id=input.session_id,
            tool_calls=[{"name": "search_knowledge_base"}],
            iterations=1,
            provider="open_source",
        )

    def list_tools(self):
        return ["search_knowledge_base"]


def test_agent_endpoint_runs_oss_agent_runner_dependency():
    app.dependency_overrides[get_agent_runner] = lambda: FakeAgentRunner()
    client = TestClient(app)

    try:
        response = client.post(
            "/v1/agents/run",
            json={"message": "Check NCC waterproofing requirements", "session_id": "s1"},
            headers={"X-User-Role": "viewer"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["response"] == "handled: Check NCC waterproofing requirements"
    assert payload["session_id"] == "s1"
    assert payload["provider"] == "open_source"
    assert payload["tool_calls"] == [{"name": "search_knowledge_base"}]


def test_rag_endpoint_calls_rest_microservice_handler(monkeypatch):
    from serving.rag import service as rag_service

    def fake_query_knowledge_base_local(request):
        assert request.question == "What does the policy say?"
        return RAGQueryResponse(
            answer="Use the policy.",
            sources=[RAGSource(document_id="policy-1", metadata={"document_type": "policy"})],
            model="gpt-4o",
            session_id=request.session_id,
        )

    monkeypatch.setattr(rag_service, "query_knowledge_base_local", fake_query_knowledge_base_local)
    client = TestClient(app)

    response = client.post(
        "/v1/rag/query",
        json={
            "question": "What does the policy say?",
            "filter_by": {"document_type": "policy"},
            "session_id": "s2",
        },
        headers={"X-User-Role": "viewer"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "Use the policy."
    assert payload["session_id"] == "s2"
    assert payload["sources"][0]["document_id"] == "policy-1"
