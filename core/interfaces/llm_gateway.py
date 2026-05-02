"""
core/interfaces/llm_gateway.py
Abstract LLM gateway contract.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


@dataclass
class CompletionRequest:
    model: str
    messages: list[dict]          # [{"role": "user", "content": "..."}]
    max_tokens: int = 1024
    temperature: float = 0.7
    stream: bool = False
    user_id: str = "anonymous"
    team_id: str = "default"
    extra: dict = field(default_factory=dict)


@dataclass
class CompletionResponse:
    id: str
    model: str
    content: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    cached: bool = False


class AbstractLLMGateway(ABC):
    """
    Uniform interface for all LLM backends.
    Implementations: LiteLLM (OSS), Azure OpenAI, Amazon Bedrock, Vertex AI.
    """

    @abstractmethod
    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Non-streaming completion."""

    @abstractmethod
    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        """Yield text chunks as they arrive."""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return available model identifiers for this provider."""
