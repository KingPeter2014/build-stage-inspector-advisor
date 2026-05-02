"""
providers/aws/governance/bedrock_guardrails.py
Amazon Bedrock Guardrails extension of the shared GuardrailRunner.

Extends the base rule engine with Amazon Bedrock Guardrails API — managed
content filtering for topics, PII, grounding, and word policies.
Falls back gracefully when BEDROCK_GUARDRAIL_ID is not configured.
"""
from __future__ import annotations

import json

import boto3

from providers.aws.config.settings import get_aws_settings
from serving.guardrails.guardrail_runner import GuardrailResult, GuardrailRunner, ViolationType


class BedrockGuardrailsRunner(GuardrailRunner):
    """
    GuardrailRunner extended with Amazon Bedrock Guardrails.

    The Bedrock Guardrail is applied AFTER the base rule engine.
    If the guardrail ID is not configured, falls back to base rules only.
    """

    def __init__(self) -> None:
        super().__init__()
        s = get_aws_settings()
        self._guardrail_id = s.bedrock_guardrail_id
        self._guardrail_version = s.bedrock_guardrail_version
        self._bedrock = boto3.client("bedrock-runtime", region_name=s.aws_region) if self._guardrail_id else None

    def _apply_guardrail(self, text: str, source: str = "INPUT") -> GuardrailResult:
        """Call Bedrock ApplyGuardrail API; return result."""
        if not self._bedrock or not self._guardrail_id:
            return GuardrailResult(allowed=True, sanitised_text=text)

        try:
            resp = self._bedrock.apply_guardrail(
                guardrailIdentifier=self._guardrail_id,
                guardrailVersion=self._guardrail_version,
                source=source,
                content=[{"text": {"text": text}}],
            )
            action = resp.get("action", "NONE")
            if action == "GUARDRAIL_INTERVENED":
                outputs = resp.get("outputs", [])
                safe_text = outputs[0]["text"] if outputs else "[Blocked by Bedrock Guardrail]"
                assessments = resp.get("assessments", [{}])
                reason = json.dumps(assessments[0]) if assessments else "Bedrock Guardrail intervened"
                return GuardrailResult(
                    allowed=False,
                    reason=reason,
                    violation_type=ViolationType.UNSAFE_OUTPUT if source == "OUTPUT" else ViolationType.TOXIC_CONTENT,
                    sanitised_text=safe_text,
                )
        except Exception:
            pass  # Fail open

        return GuardrailResult(allowed=True, sanitised_text=text)

    def check_input(self, text: str) -> GuardrailResult:
        base = super().check_input(text)
        if not base.allowed:
            return base
        return self._apply_guardrail(text, source="INPUT")

    def check_output(self, text: str) -> GuardrailResult:
        base = super().check_output(text)
        checked_text = base.sanitised_text or text
        bedrock_result = self._apply_guardrail(checked_text, source="OUTPUT")
        if not bedrock_result.allowed:
            return GuardrailResult(
                allowed=True,   # Output violations sanitise, not block
                reason=bedrock_result.reason,
                violation_type=bedrock_result.violation_type,
                sanitised_text=bedrock_result.sanitised_text,
            )
        return base
