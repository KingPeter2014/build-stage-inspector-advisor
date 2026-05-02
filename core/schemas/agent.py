"""
core/schemas/agent.py
Canonical agent input/output models shared by all provider agent runners.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentInput(BaseModel):
    message: str
    session_id: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    mode: str = "single"   # "single" | "multi"


class AgentOutput(BaseModel):
    response: str
    session_id: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    iterations: int = 0
    blocked: bool = False
    block_reason: str = ""
    provider: str = ""
