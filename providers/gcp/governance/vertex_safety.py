"""
providers/gcp/governance/vertex_safety.py
Vertex AI Safety + Perspective API guardrails extension.

Extends the shared GuardrailRunner with:
  1. Vertex AI built-in safety filters (checked automatically by the Gemini API).
  2. Perspective API toxicity scoring for explicit content moderation.
"""
from __future__ import annotations

import json

import requests

from providers.gcp.config.settings import get_gcp_settings
from serving.guardrails.guardrail_runner import GuardrailResult, GuardrailRunner, ViolationType


class VertexSafetyGuardrails(GuardrailRunner):
    """
    GuardrailRunner extended with Perspective API toxicity scoring.

    Vertex AI Gemini models apply safety filters automatically at generation time.
    This class adds an explicit Perspective API check on input text for
    TOXICITY, SEVERE_TOXICITY, IDENTITY_ATTACK, and THREAT attributes.
    Falls back to base rules when PERSPECTIVE_API_KEY is not configured.
    """

    ATTRIBUTES = ["TOXICITY", "SEVERE_TOXICITY", "IDENTITY_ATTACK", "THREAT"]

    def __init__(self) -> None:
        super().__init__()
        s = get_gcp_settings()
        self._api_key = s.perspective_api_key
        self._threshold = s.perspective_threshold
        self._api_url = (
            f"https://commentanalyzer.googleapis.com/v1alpha1/comments:analyze"
            f"?key={self._api_key}"
        )

    def _perspective_score(self, text: str) -> tuple[float, str]:
        """Return (max_score, attribute_name) from Perspective API."""
        if not self._api_key:
            return 0.0, ""
        try:
            body = {
                "comment": {"text": text},
                "requestedAttributes": {attr: {} for attr in self.ATTRIBUTES},
                "languages": ["en"],
            }
            resp = requests.post(self._api_url, json=body, timeout=5)
            if resp.status_code != 200:
                return 0.0, ""
            scores = resp.json().get("attributeScores", {})
            max_score, max_attr = 0.0, ""
            for attr, data in scores.items():
                score = data["summaryScore"]["value"]
                if score > max_score:
                    max_score, max_attr = score, attr
            return max_score, max_attr
        except Exception:
            return 0.0, ""

    def check_input(self, text: str) -> GuardrailResult:
        base = super().check_input(text)
        if not base.allowed:
            return base

        score, attr = self._perspective_score(text)
        if score >= self._threshold:
            return GuardrailResult(
                allowed=False,
                reason=f"Perspective API flagged input: {attr} score={score:.2f}",
                violation_type=ViolationType.TOXIC_CONTENT,
            )

        return GuardrailResult(allowed=True, sanitised_text=text)

    def check_output(self, text: str) -> GuardrailResult:
        base = super().check_output(text)
        checked_text = base.sanitised_text or text

        score, attr = self._perspective_score(checked_text)
        if score >= self._threshold:
            return GuardrailResult(
                allowed=True,
                reason=f"Perspective API flagged output: {attr} score={score:.2f}",
                violation_type=ViolationType.UNSAFE_OUTPUT,
                sanitised_text="[Content removed by safety policy]",
            )

        return base
