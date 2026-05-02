"""
core/schemas/chat.py
Canonical request/response models shared by all provider gateways.
All provider FastAPI apps import from here so the API surface is identical.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "gpt-4o"
    messages: list[ChatMessage]
    max_tokens: int = Field(default=1024, ge=1, le=32768)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    stream: bool = False
    user_id: str | None = None
    team_id: str | None = None


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


class ChatResponse(BaseModel):
    id: str
    model: str
    content: str
    usage: UsageInfo
    cached: bool = False
    provider: str = ""  # "open_source" | "azure" | "aws" | "gcp"
