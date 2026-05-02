"""
providers/open_source/serving/gateway
Re-exports the LiteLLM/FastAPI gateway and wires it to AbstractLLMGateway.
"""
from serving.gateway.app import app, ChatRequest, ChatResponse  # noqa: F401

from core.interfaces.llm_gateway import (
    AbstractLLMGateway,
    CompletionRequest,
    CompletionResponse,
)
import litellm
from litellm import acompletion
from typing import AsyncIterator


class LiteLLMGateway(AbstractLLMGateway):
    """AbstractLLMGateway backed by LiteLLM (supports OpenAI, Anthropic, local models)."""

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        response = await acompletion(
            model=request.model,
            messages=request.messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        cost = litellm.completion_cost(completion_response=response)
        usage = response.usage
        return CompletionResponse(
            id=response.id,
            model=response.model,
            content=response.choices[0].message.content or "",
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            estimated_cost_usd=cost,
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[str]:
        response = await acompletion(
            model=request.model,
            messages=request.messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def list_models(self) -> list[str]:
        return ["gpt-4o", "gpt-4o-mini", "claude-sonnet", "claude-haiku"]
