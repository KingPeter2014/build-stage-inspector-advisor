"""
Canonical REST schemas for RAG microservice calls.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    question: str
    filter_by: dict[str, Any] = Field(default_factory=dict)
    acl_filter: dict[str, Any] = Field(default_factory=dict)
    top_k: int = 5
    session_id: str = ""


class RAGSource(BaseModel):
    document_id: str = ""
    chunk_id: str = ""
    score: float = 0.0
    content: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class RAGQueryResponse(BaseModel):
    answer: str
    sources: list[RAGSource] = Field(default_factory=list)
    prompt_version: int = 0
    model: str = ""
    usage: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
