"""
providers/azure/serving/gateway/app.py
FastAPI LLM gateway backed by Azure OpenAI Service.

Implements the same /v1/chat/completions endpoint as the OSS gateway so
clients are fully interchangeable. Uses core schemas for request/response
models and wires the shared policy stack (RBAC, guardrails, budget, audit).

Run: uvicorn providers.azure.serving.gateway.app:app --port 4001
"""
from __future__ import annotations

import time

import structlog
from fastapi import Depends, FastAPI, HTTPException
from openai import AsyncAzureOpenAI

from core.schemas.chat import ChatRequest, ChatResponse, UsageInfo
from observability.tracing.tracer import get_tracer
from observability.metrics.prometheus_metrics import (
    latency_histogram, request_counter, token_counter,
)
from providers.azure.config.settings import get_azure_settings
from serving.cache.semantic_cache import SemanticCache
from serving.gateway.policy import PolicyContext, get_policy_context

log = structlog.get_logger()
app = FastAPI(title="LLMOps Gateway — Azure AI Foundry", version="1.0.0")
tracer = get_tracer("gateway.azure")

_settings = get_azure_settings()
_client = AsyncAzureOpenAI(
    azure_endpoint=_settings.azure_openai_endpoint,
    api_key=_settings.azure_openai_api_key,
    api_version=_settings.azure_openai_api_version,
)
_cache = SemanticCache(
    similarity_threshold=0.92,
    ttl_seconds=3600,
    redis_url=_settings.azure_redis_url or None,
)


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "azure", "cache_size": _cache.size}


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    ctx: PolicyContext = Depends(get_policy_context),
):
    start = time.perf_counter()

    with tracer.start_as_current_span("chat_completion.azure") as span:
        span.set_attribute("model", req.model)
        span.set_attribute("user_id", ctx.user.id)

        # Policy stack: rate limit → RBAC → input guardrails
        ctx.enforce_rate_limit()
        ctx.enforce_permission("chat:completion", req.model)
        last_user_msg = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        ctx.check_input(last_user_msg)

        # Semantic cache lookup
        cache_key = f"azure::{req.model}::{last_user_msg}"
        cached = _cache.get(cache_key)
        if cached:
            span.set_attribute("cache_hit", True)
            request_counter.labels(model=req.model, team=ctx.user.team_id, status="cache_hit").inc()
            return ChatResponse(
                id="cached",
                model=req.model,
                content=cached,
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0, estimated_cost_usd=0.0),
                cached=True,
                provider="azure",
            )

        # Budget gate
        estimated_tokens = sum(len(m.content.split()) * 1.3 for m in req.messages) + req.max_tokens
        ctx.enforce_budget(estimated_tokens * 0.000002)

        try:
            messages = [{"role": m.role, "content": m.content} for m in req.messages]
            response = await _client.chat.completions.create(
                model=_settings.azure_openai_deployment_name,
                messages=messages,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
            )

            latency = time.perf_counter() - start
            usage = response.usage
            content = response.choices[0].message.content or ""

            # Output guardrails (sanitise PII)
            out_result = ctx.check_output(content)
            safe_content = out_result.sanitised_text or content

            _cache.set(cache_key, safe_content)

            # Cost estimate: Azure OpenAI pricing (gpt-4o ~$5/1M prompt, $15/1M completion)
            cost = (usage.prompt_tokens * 5e-6) + (usage.completion_tokens * 15e-6)
            ctx.record_cost(req.model, usage.prompt_tokens, usage.completion_tokens, cost)
            ctx.audit("chat_completion", req.model, last_user_msg, safe_content,
                      guardrail_result=out_result, prompt_tokens=usage.prompt_tokens,
                      completion_tokens=usage.completion_tokens, estimated_cost_usd=cost)

            request_counter.labels(model=req.model, team=ctx.user.team_id, status="success").inc()
            token_counter.labels(model=req.model, token_type="prompt").inc(usage.prompt_tokens)
            token_counter.labels(model=req.model, token_type="completion").inc(usage.completion_tokens)
            latency_histogram.labels(model=req.model).observe(latency)

            return ChatResponse(
                id=response.id,
                model=response.model,
                content=safe_content,
                usage=UsageInfo(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    estimated_cost_usd=cost,
                ),
                provider="azure",
            )

        except HTTPException:
            raise
        except Exception as e:
            request_counter.labels(model=req.model, team=ctx.user.team_id, status="error").inc()
            span.record_exception(e)
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("providers.azure.serving.gateway.app:app", host="0.0.0.0", port=4001, reload=True)
