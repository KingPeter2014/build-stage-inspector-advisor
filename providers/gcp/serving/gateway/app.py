"""
providers/gcp/serving/gateway/app.py
FastAPI LLM gateway backed by Vertex AI Model Garden (Gemini).

Exposes the same /v1/chat/completions contract as all other provider gateways.
Uses the google-cloud-aiplatform SDK (vertexai) for Gemini model access.

Run: uvicorn providers.gcp.serving.gateway.app:app --port 4003
"""
from __future__ import annotations

import time

import structlog
import vertexai
from fastapi import Depends, FastAPI, HTTPException
from vertexai.generative_models import GenerativeModel, Content, Part

from core.schemas.chat import ChatRequest, ChatResponse, UsageInfo
from observability.metrics.prometheus_metrics import (
    latency_histogram, request_counter, token_counter,
)
from observability.tracing.tracer import get_tracer
from providers.gcp.config.settings import get_gcp_settings
from serving.cache.semantic_cache import SemanticCache
from serving.gateway.policy import PolicyContext, get_policy_context

log = structlog.get_logger()
app = FastAPI(title="LLMOps Gateway — GCP Vertex AI", version="1.0.0")
tracer = get_tracer("gateway.gcp")

_settings = get_gcp_settings()
vertexai.init(project=_settings.gcp_project_id, location=_settings.gcp_region)
_cache = SemanticCache(
    similarity_threshold=0.92,
    ttl_seconds=3600,
    redis_url=_settings.gcp_redis_url or None,
)

# Gemini pricing (USD per 1K tokens) — update as needed
_PRICE_MAP = {
    "gemini-1.5-pro-002": (0.00125, 0.005),
    "gemini-1.5-flash-002": (0.000075, 0.0003),
    "gemini-2.0-flash-001": (0.0001, 0.0004),
}


def _estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_p, out_p = _PRICE_MAP.get(model_id, (0.001, 0.002))
    return (prompt_tokens * in_p + completion_tokens * out_p) / 1000


def _to_vertex_contents(messages) -> tuple[list[Content], str | None]:
    """Convert ChatMessage list to Vertex AI Content objects + system instruction."""
    system_instruction = None
    contents: list[Content] = []
    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content
        elif msg.role in ("user", "assistant"):
            role = "user" if msg.role == "user" else "model"
            contents.append(Content(role=role, parts=[Part.from_text(msg.content)]))
    return contents, system_instruction


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "gcp", "cache_size": _cache.size}


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    ctx: PolicyContext = Depends(get_policy_context),
):
    start = time.perf_counter()
    model_id = req.model if req.model.startswith("gemini") else _settings.vertex_model_id

    with tracer.start_as_current_span("chat_completion.gcp") as span:
        span.set_attribute("model", model_id)
        span.set_attribute("user_id", ctx.user.id)

        ctx.enforce_rate_limit()
        ctx.enforce_permission("chat:completion", req.model)
        last_user_msg = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        ctx.check_input(last_user_msg)

        cache_key = f"gcp::{model_id}::{last_user_msg}"
        cached = _cache.get(cache_key)
        if cached:
            span.set_attribute("cache_hit", True)
            request_counter.labels(model=model_id, team=ctx.user.team_id, status="cache_hit").inc()
            return ChatResponse(
                id="cached", model=model_id, content=cached,
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0, estimated_cost_usd=0.0),
                cached=True, provider="gcp",
            )

        estimated_tokens = sum(len(m.content.split()) * 1.3 for m in req.messages) + req.max_tokens
        ctx.enforce_budget(estimated_tokens * 0.000002)

        try:
            contents, system_instruction = _to_vertex_contents(req.messages)
            model = GenerativeModel(
                model_id,
                system_instruction=system_instruction,
            )
            response = model.generate_content(
                contents,
                generation_config={
                    "max_output_tokens": req.max_tokens,
                    "temperature": req.temperature,
                },
            )

            latency = time.perf_counter() - start
            content = response.text or ""
            usage_meta = response.usage_metadata
            prompt_tokens = usage_meta.prompt_token_count if usage_meta else 0
            completion_tokens = usage_meta.candidates_token_count if usage_meta else 0
            cost = _estimate_cost(model_id, prompt_tokens, completion_tokens)

            out_result = ctx.check_output(content)
            safe_content = out_result.sanitised_text or content

            _cache.set(cache_key, safe_content)
            ctx.record_cost(model_id, prompt_tokens, completion_tokens, cost)
            ctx.audit("chat_completion", model_id, last_user_msg, safe_content,
                      guardrail_result=out_result, prompt_tokens=prompt_tokens,
                      completion_tokens=completion_tokens, estimated_cost_usd=cost)

            request_counter.labels(model=model_id, team=ctx.user.team_id, status="success").inc()
            token_counter.labels(model=model_id, token_type="prompt").inc(prompt_tokens)
            token_counter.labels(model=model_id, token_type="completion").inc(completion_tokens)
            latency_histogram.labels(model=model_id).observe(latency)

            return ChatResponse(
                id=str(response._raw_response.response_id) if hasattr(response, "_raw_response") else "",
                model=model_id,
                content=safe_content,
                usage=UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                                total_tokens=prompt_tokens + completion_tokens,
                                estimated_cost_usd=cost),
                provider="gcp",
            )

        except HTTPException:
            raise
        except Exception as e:
            request_counter.labels(model=model_id, team=ctx.user.team_id, status="error").inc()
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("providers.gcp.serving.gateway.app:app", host="0.0.0.0", port=4003, reload=True)
