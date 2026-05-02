"""
serving/gateway/app.py
LiteLLM-powered LLM gateway with:
  - Two-level semantic response cache (exact + similarity)
  - Runtime policy enforcement: rate limit → RBAC → input guardrails → budget → output guardrails
  - Tamper-evident audit logging
  - OpenTelemetry tracing + Prometheus metrics
Run: uvicorn serving.gateway.app:app --port 4000
"""
from __future__ import annotations

import os
import time

import litellm
import structlog
from fastapi import Depends, FastAPI, HTTPException
from litellm import acompletion
from pydantic import BaseModel

from observability.metrics.prometheus_metrics import (
    latency_histogram,
    request_counter,
    token_counter,
)
from observability.tracing.tracer import get_tracer
from serving.cache.semantic_cache import SemanticCache
from serving.gateway.policy import PolicyContext, get_policy_context

log = structlog.get_logger()
app = FastAPI(title="LLMOps Gateway", version="1.0.0")
tracer = get_tracer("gateway")

# Semantic cache: exact-match + cosine-similarity fallback, 1-hour TTL
_cache = SemanticCache(
    similarity_threshold=0.92,
    ttl_seconds=3600,
    redis_url=os.getenv("REDIS_URL"),  # falls back to in-process dict when unset
)


# ── Request / Response models ──────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "gpt-4o"
    messages: list[ChatMessage]
    max_tokens: int = 1024
    temperature: float = 0.7
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


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "cache_size": _cache.size}


# ── Chat completion endpoint ───────────────────────────────────────────────────

@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    ctx: PolicyContext = Depends(get_policy_context),
):
    start = time.perf_counter()

    with tracer.start_as_current_span("chat_completion") as span:
        span.set_attribute("model", req.model)
        span.set_attribute("user_id", ctx.user.id)
        span.set_attribute("team_id", ctx.user.team_id)

        # ── 1. Rate limiting ───────────────────────────────────────────────────
        ctx.enforce_rate_limit()

        # ── 2. RBAC ───────────────────────────────────────────────────────────
        ctx.enforce_permission("chat:completion", req.model)

        # ── 3. Input guardrails ───────────────────────────────────────────────
        last_user_msg = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        input_result = ctx.check_input(last_user_msg)

        # ── 4. Semantic cache lookup ──────────────────────────────────────────
        cache_key = f"{req.model}::{last_user_msg}"
        cached_response = _cache.get(cache_key)
        if cached_response:
            span.set_attribute("cache_hit", True)
            log.info("cache_hit", model=req.model, user_id=ctx.user.id)
            request_counter.labels(model=req.model, team=ctx.user.team_id, status="cache_hit").inc()
            return ChatResponse(
                id="cached",
                model=req.model,
                content=cached_response,
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0, estimated_cost_usd=0.0),
                cached=True,
            )

        # ── 5. Budget gate (conservative pre-check) ───────────────────────────
        # Rough estimate: 1 token ≈ $0.000002 for gpt-4o; gates runaway spend
        estimated_tokens = sum(len(m.content.split()) * 1.3 for m in req.messages) + req.max_tokens
        estimated_cost = estimated_tokens * 0.000002
        ctx.enforce_budget(estimated_cost)

        try:
            # ── 6. LLM call ───────────────────────────────────────────────────
            messages = [m.model_dump() for m in req.messages]
            response = await acompletion(
                model=req.model,
                messages=messages,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
            )

            latency = time.perf_counter() - start
            usage = response.usage
            actual_cost = litellm.completion_cost(completion_response=response)
            output_text = response.choices[0].message.content or ""

            # ── 7. Output guardrails (sanitise, never block) ──────────────────
            output_result = ctx.check_output(output_text)
            safe_output = output_result.sanitised_text or output_text

            # ── 8. Store in semantic cache ────────────────────────────────────
            _cache.set(cache_key, safe_output)

            # ── 9. Record actual cost ─────────────────────────────────────────
            ctx.record_cost(
                model=req.model,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cost_usd=actual_cost,
            )

            # ── 10. Audit log ─────────────────────────────────────────────────
            ctx.audit(
                action="chat_completion",
                model=req.model,
                input_text=last_user_msg,
                output_text=safe_output,
                guardrail_result=output_result,
                trace_id=span.get_span_context().trace_id if hasattr(span.get_span_context(), "trace_id") else "",
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                estimated_cost_usd=actual_cost,
            )

            # ── Metrics ───────────────────────────────────────────────────────
            request_counter.labels(model=req.model, team=ctx.user.team_id, status="success").inc()
            token_counter.labels(model=req.model, token_type="prompt").inc(usage.prompt_tokens)
            token_counter.labels(model=req.model, token_type="completion").inc(usage.completion_tokens)
            latency_histogram.labels(model=req.model).observe(latency)

            span.set_attribute("prompt_tokens", usage.prompt_tokens)
            span.set_attribute("completion_tokens", usage.completion_tokens)
            span.set_attribute("latency_seconds", latency)
            span.set_attribute("cache_hit", False)
            span.set_attribute("pii_redacted", output_result.violation_type is not None)

            log.info("chat_completion", model=req.model, latency=latency, cost=actual_cost,
                     user_id=ctx.user.id, team_id=ctx.user.team_id)

            return ChatResponse(
                id=response.id,
                model=response.model,
                content=safe_output,
                usage=UsageInfo(
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    estimated_cost_usd=actual_cost,
                ),
                cached=False,
            )

        except HTTPException:
            raise
        except Exception as e:
            request_counter.labels(model=req.model, team=ctx.user.team_id, status="error").inc()
            span.record_exception(e)
            log.error("chat_completion_error", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("serving.gateway.app:app", host="0.0.0.0", port=4000, reload=True)
