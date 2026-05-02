"""
serving/gateway/policy.py
Runtime policy enforcement stack wired as a FastAPI dependency.

Every request through the gateway passes this stack in order:
  1. Rate limiting     — token-bucket per user (60 req/min default)
  2. RBAC              — role + model allowlist check
  3. Input guardrails  — injection / PII / toxicity scan
  4. Budget gate       — per-request / daily / monthly spend limits
  5. Output guardrails — PII redaction on LLM response (called post-LLM)
  6. Audit logging     — tamper-evident record of every interaction

Usage in an endpoint:
    @app.post("/v1/chat/completions")
    async def chat(req: ChatRequest, ctx: PolicyContext = Depends(get_policy_context)):
        ctx.enforce_rate_limit()
        ctx.enforce_permission("chat:completion", req.model)
        input_result = ctx.check_input(last_user_message)
        ctx.enforce_budget(estimated_cost=0.01)
        # … call LLM …
        output_result = ctx.check_output(llm_text)
        ctx.record_cost(...)
        ctx.audit(...)
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException

from governance.access_control.rbac import AccessDenied, RBACEnforcer, Role, User
from governance.audit.audit_logger import AuditConfig, AuditLogger
from governance.cost.cost_manager import BudgetPolicy, CostManager, CostRecord
from serving.guardrails.guardrail_runner import GuardrailResult, GuardrailRunner


# ── Singletons (module-level, shared across requests) ─────────────────────────

_rbac = RBACEnforcer()
_guardrails = GuardrailRunner()
_cost = CostManager()
_audit = AuditLogger(AuditConfig(store_full_content=False, redact_pii=True))

# Default budget policy — teams with custom policies should call register_policy()
_cost.register_policy(BudgetPolicy(
    team_id="default",
    daily_limit_usd=50.0,
    monthly_limit_usd=1000.0,
    per_request_limit_usd=1.0,
))


# ── Token-bucket rate limiter ─────────────────────────────────────────────────

class _TokenBucketLimiter:
    """
    Per-user token-bucket rate limiter.
    Default: 60 requests/minute with burst capacity of 60.
    """

    def __init__(self, rate_per_minute: float = 60.0, burst: int = 60) -> None:
        self._rate = rate_per_minute / 60.0  # tokens/second
        self._burst = burst
        self._buckets: dict[str, dict[str, float]] = defaultdict(
            lambda: {"tokens": float(burst), "ts": time.monotonic()}
        )
        self._lock = threading.Lock()

    def allow(self, user_id: str) -> bool:
        with self._lock:
            b = self._buckets[user_id]
            now = time.monotonic()
            elapsed = now - b["ts"]
            b["tokens"] = min(self._burst, b["tokens"] + elapsed * self._rate)
            b["ts"] = now
            if b["tokens"] >= 1.0:
                b["tokens"] -= 1.0
                return True
            return False


_rate_limiter = _TokenBucketLimiter()


# ── User resolution ───────────────────────────────────────────────────────────

def resolve_user(
    x_user_id: str = Header(default="anonymous"),
    x_user_role: str = Header(default="viewer"),
    x_team_id: str = Header(default="default"),
) -> User:
    """
    Extract user identity from request headers.
    In production, replace with JWT validation or an OAuth2 dependency.
    Expected headers:
        X-User-Id   — unique user identifier
        X-User-Role — one of: viewer, developer, ml_engineer, admin
        X-Team-Id   — team / cost-centre identifier
    """
    try:
        role = Role(x_user_role.lower())
    except ValueError:
        role = Role.VIEWER
    return User(id=x_user_id, role=role, team_id=x_team_id)


# ── Policy context ────────────────────────────────────────────────────────────

@dataclass
class PolicyContext:
    """
    Holds all policy services for a single request.
    Passed into endpoint handlers via FastAPI Depends.
    """
    user: User

    # ── 1. Rate limiting ──────────────────────────────────────────────────────

    def enforce_rate_limit(self) -> None:
        if not _rate_limiter.allow(self.user.id):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded — maximum 60 requests per minute.",
            )

    # ── 2. RBAC ───────────────────────────────────────────────────────────────

    def enforce_permission(self, permission: str, model: str) -> None:
        try:
            _rbac.enforce(self.user, permission)
            _rbac.enforce_model_access(self.user, model)
        except AccessDenied as exc:
            raise HTTPException(status_code=403, detail=str(exc))

    # ── 3 & 5. Guardrails ─────────────────────────────────────────────────────

    def check_input(self, text: str) -> GuardrailResult:
        result = _guardrails.check_input(text)
        if not result.allowed:
            raise HTTPException(
                status_code=422,
                detail=f"Input policy violation [{result.violation_type}]: {result.reason}",
            )
        return result

    def check_output(self, text: str) -> GuardrailResult:
        """Returns sanitised result; never raises (output violations are redacted, not blocked)."""
        return _guardrails.check_output(text)

    # ── 4. Budget enforcement ─────────────────────────────────────────────────

    def enforce_budget(self, estimated_cost_usd: float) -> None:
        result = _cost.check_budget(self.user.team_id, estimated_cost_usd)
        if not result["allowed"]:
            raise HTTPException(
                status_code=402,
                detail=f"Budget policy blocked request: {result['reason']} "
                       f"(limit=${result.get('limit', '?'):.4f})",
            )

    # ── Cost recording ────────────────────────────────────────────────────────

    def record_cost(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost_usd: float,
    ) -> None:
        from datetime import datetime
        _cost.record(CostRecord(
            timestamp=datetime.utcnow().isoformat(),
            user_id=self.user.id,
            team_id=self.user.team_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        ))

    # ── 6. Audit logging ──────────────────────────────────────────────────────

    def audit(
        self,
        action: str,
        model: str,
        input_text: str,
        output_text: str,
        guardrail_result: GuardrailResult | None = None,
        trace_id: str = "",
        **extra: Any,
    ) -> None:
        _audit.log(
            action=action,
            model=model,
            input_text=input_text,
            output_text=output_text,
            user_id=self.user.id,
            team_id=self.user.team_id,
            trace_id=trace_id,
            pii_detected=guardrail_result is not None and guardrail_result.violation_type is not None,
            guardrail_triggered=guardrail_result is not None and not guardrail_result.allowed,
            guardrail_type=guardrail_result.violation_type.value if guardrail_result and guardrail_result.violation_type else "",
            **extra,
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_policy_context(user: User = Depends(resolve_user)) -> PolicyContext:
    return PolicyContext(user=user)
