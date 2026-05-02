"""
providers/aws/serving/gateway/app.py
FastAPI LLM gateway backed by Amazon Bedrock Runtime.

Exposes the same /v1/chat/completions contract as the OSS and Azure gateways.
Supports Claude, Llama, Titan, and other Bedrock-hosted models via the
Converse API (unified multi-turn interface).

Run: uvicorn providers.aws.serving.gateway.app:app --port 4002
"""
from __future__ import annotations

import json
import time

import boto3
import structlog
from fastapi import Depends, FastAPI, HTTPException

from core.schemas.chat import ChatRequest, ChatResponse, UsageInfo
from observability.metrics.prometheus_metrics import (
    latency_histogram, request_counter, token_counter,
)
from observability.tracing.tracer import get_tracer
from providers.aws.config.settings import get_aws_settings
from serving.cache.semantic_cache import SemanticCache
from serving.gateway.policy import PolicyContext, get_policy_context

log = structlog.get_logger()
app = FastAPI(title="LLMOps Gateway — AWS Bedrock", version="1.0.0")
tracer = get_tracer("gateway.aws")

_settings = get_aws_settings()
_bedrock = boto3.client("bedrock-runtime", region_name=_settings.aws_region)
_cache = SemanticCache(
    similarity_threshold=0.92,
    ttl_seconds=3600,
    redis_url=_settings.aws_redis_url or None,
)

# Bedrock Converse API pricing map (USD per 1K tokens) — update as needed
_PRICE_MAP: dict[str, tuple[float, float]] = {
    "anthropic.claude-3-5-sonnet-20241022-v2:0": (0.003, 0.015),
    "anthropic.claude-3-haiku-20240307-v1:0": (0.00025, 0.00125),
    "amazon.titan-text-express-v1": (0.0008, 0.0016),
}


def _estimate_cost(model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
    in_price, out_price = _PRICE_MAP.get(model_id, (0.001, 0.003))
    return (prompt_tokens * in_price + completion_tokens * out_price) / 1000


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "aws", "cache_size": _cache.size}


@app.post("/v1/chat/completions", response_model=ChatResponse)
async def chat_completions(
    req: ChatRequest,
    ctx: PolicyContext = Depends(get_policy_context),
):
    start = time.perf_counter()
    model_id = req.model if "/" not in req.model else _settings.bedrock_model_id

    with tracer.start_as_current_span("chat_completion.aws") as span:
        span.set_attribute("model", model_id)
        span.set_attribute("user_id", ctx.user.id)

        ctx.enforce_rate_limit()
        ctx.enforce_permission("chat:completion", req.model)
        last_user_msg = next(
            (m.content for m in reversed(req.messages) if m.role == "user"), ""
        )
        ctx.check_input(last_user_msg)

        cache_key = f"aws::{model_id}::{last_user_msg}"
        cached = _cache.get(cache_key)
        if cached:
            span.set_attribute("cache_hit", True)
            request_counter.labels(model=model_id, team=ctx.user.team_id, status="cache_hit").inc()
            return ChatResponse(
                id="cached", model=model_id, content=cached,
                usage=UsageInfo(prompt_tokens=0, completion_tokens=0, total_tokens=0, estimated_cost_usd=0.0),
                cached=True, provider="aws",
            )

        estimated_tokens = sum(len(m.content.split()) * 1.3 for m in req.messages) + req.max_tokens
        ctx.enforce_budget(estimated_tokens * 0.000002)

        try:
            # Bedrock Converse API — unified multi-turn interface
            converse_messages = [
                {"role": m.role, "content": [{"text": m.content}]}
                for m in req.messages
                if m.role in ("user", "assistant")
            ]
            system_msgs = [
                {"text": m.content} for m in req.messages if m.role == "system"
            ]

            kwargs: dict = dict(
                modelId=model_id,
                messages=converse_messages,
                inferenceConfig={"maxTokens": req.max_tokens, "temperature": req.temperature},
            )
            if system_msgs:
                kwargs["system"] = system_msgs

            response = _bedrock.converse(**kwargs)

            latency = time.perf_counter() - start
            content = response["output"]["message"]["content"][0]["text"]
            usage_meta = response.get("usage", {})
            prompt_tokens = usage_meta.get("inputTokens", 0)
            completion_tokens = usage_meta.get("outputTokens", 0)
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
                id=response.get("ResponseMetadata", {}).get("RequestId", ""),
                model=model_id,
                content=safe_content,
                usage=UsageInfo(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                                total_tokens=prompt_tokens + completion_tokens,
                                estimated_cost_usd=cost),
                provider="aws",
            )

        except HTTPException:
            raise
        except Exception as e:
            request_counter.labels(model=model_id, team=ctx.user.team_id, status="error").inc()
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("providers.aws.serving.gateway.app:app", host="0.0.0.0", port=4002, reload=True)
