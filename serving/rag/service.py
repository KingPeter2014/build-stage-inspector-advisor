"""
Service helpers for using the RAG pipeline as application and agent tools.
"""
from __future__ import annotations

from typing import Any

import httpx

from core.schemas.rag import RAGQueryRequest, RAGQueryResponse, RAGSource

def default_collection_name(env: str | None = None) -> str:
    from config.settings import get_settings

    settings = get_settings()
    if settings.qdrant_collection_name:
        return settings.qdrant_collection_name
    return f"buildstage_documents_{env or settings.app_env}"


def build_default_rag_pipeline(top_k: int = 5):
    """
    Build the default Qdrant-backed RAG pipeline lazily.

    Keeping imports inside this function lets unit tests and gateway startup
    avoid loading embedding models until a RAG query is actually requested.
    """
    from config.settings import get_settings
    from serving.rag.pipeline import RAGPipeline
    from storage.prompt_registry.registry import LocalPromptRegistry
    from storage.vector_store.qdrant_store import QdrantVectorStore

    settings = get_settings()
    vector_store = QdrantVectorStore(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
        collection_name=default_collection_name(),
    )
    return RAGPipeline(
        vector_store=vector_store,
        prompt_registry=LocalPromptRegistry(),
        model=settings.default_model,
        top_k=top_k,
    )


def build_filter(
    document_type: str = "",
    tenant_id: str = "",
    inspection_stage: str = "",
    jurisdiction: str = "",
    building_class: str = "",
    project_id: str = "",
    contract_id: str = "",
    document_family: str = "",
    source_version: str = "",
    trust_level: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {
        "document_type": document_type,
        "tenant_id": tenant_id,
        "inspection_stage": inspection_stage,
        "jurisdiction": jurisdiction,
        "building_class": building_class,
        "project_id": project_id,
        "contract_id": contract_id,
        "document_family": document_family,
        "source_version": source_version,
        "trust_level": trust_level,
    }
    if tags:
        filters["tags"] = tags
    return {key: value for key, value in filters.items() if value not in ("", None, [])}


def rag_response_to_schema(response: Any, session_id: str = "") -> RAGQueryResponse:
    sources = []
    for source in getattr(response, "sources", []):
        sources.append(RAGSource(
            document_id=getattr(source, "document_id", ""),
            chunk_id=getattr(source, "chunk_id", ""),
            score=float(getattr(source, "score", 0.0) or 0.0),
            content=getattr(source, "content", ""),
            metadata=getattr(source, "metadata", {}) or {},
        ))
    return RAGQueryResponse(
        answer=getattr(response, "answer", str(response)),
        sources=sources,
        prompt_version=int(getattr(response, "prompt_version", 0) or 0),
        model=getattr(response, "model", ""),
        usage=getattr(response, "usage", {}) or {},
        session_id=session_id,
    )


def format_rag_response(response: Any) -> str:
    citations = []
    for source in getattr(response, "sources", []):
        metadata = getattr(source, "metadata", {}) or {}
        title = metadata.get("source_title") or metadata.get("filename") or getattr(source, "document_id", "")
        clause = metadata.get("clause") or metadata.get("section") or metadata.get("volume") or ""
        label = f"{title} {clause}".strip()
        if label and label not in citations:
            citations.append(label)

    answer = getattr(response, "answer", str(response))
    if not citations:
        return answer
    return f"{answer}\n\nSources: " + "; ".join(citations[:5])


def query_knowledge_base_local(
    request: RAGQueryRequest,
    pipeline: Any | None = None,
) -> RAGQueryResponse:
    rag_pipeline = pipeline or build_default_rag_pipeline(top_k=request.top_k)
    response = rag_pipeline.query(
        question=request.question,
        filter_by=request.filter_by or None,
        acl_filter=request.acl_filter or None,
    )
    return rag_response_to_schema(response, session_id=request.session_id)


def query_knowledge_base_api(
    request: RAGQueryRequest,
    api_url: str = "",
    timeout_seconds: float = 60.0,
) -> RAGQueryResponse:
    if not api_url:
        from config.settings import get_settings

        api_url = get_settings().rag_api_url

    response = httpx.post(
        api_url,
        json=request.model_dump(),
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return RAGQueryResponse.model_validate(response.json())


def search_knowledge_base_text(
    query: str,
    document_type: str = "",
    tenant_id: str = "",
    inspection_stage: str = "",
    jurisdiction: str = "",
    building_class: str = "",
    project_id: str = "",
    contract_id: str = "",
    document_family: str = "",
    source_version: str = "",
    trust_level: str = "",
    tags: list[str] | None = None,
    top_k: int = 5,
    api_url: str = "",
    pipeline: Any | None = None,
) -> str:
    """Run a RAG query and return a compact text response for agent tools."""
    request = RAGQueryRequest(
        question=query,
        filter_by=build_filter(
            document_type=document_type,
            tenant_id=tenant_id,
            inspection_stage=inspection_stage,
            jurisdiction=jurisdiction,
            building_class=building_class,
            project_id=project_id,
            contract_id=contract_id,
            document_family=document_family,
            source_version=source_version,
            trust_level=trust_level,
            tags=tags,
        ),
        top_k=top_k,
    )
    response = (
        query_knowledge_base_local(request, pipeline=pipeline)
        if pipeline is not None
        else query_knowledge_base_api(request, api_url=api_url)
    )
    return format_rag_response(response)
