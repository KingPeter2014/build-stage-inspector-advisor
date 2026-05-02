"""
providers/azure/governance/content_safety.py
Azure Content Safety guardrails extension.

Extends the shared GuardrailRunner with Azure Content Safety API calls for
hate speech, self-harm, sexual content, and violence detection — giving the
Azure stack managed, continuously-updated content moderation at the API level.
"""
from __future__ import annotations

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import (
    AnalyzeTextOptions,
    TextCategory,
)
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

from serving.guardrails.guardrail_runner import GuardrailResult, GuardrailRunner, ViolationType
from providers.azure.config.settings import get_azure_settings


class AzureContentSafetyGuardrails(GuardrailRunner):
    """
    GuardrailRunner extended with Azure Content Safety API.

    Falls back gracefully to the base rule-based engine if Content Safety
    is unreachable or the API key is not configured.

    Severity thresholds follow Azure recommendations:
      0–2: Safe  |  4: Low  |  6: Medium  |  8: High
    """

    # Block anything at medium severity (6) or above
    SEVERITY_THRESHOLD = 6

    def __init__(self, severity_threshold: int = 6) -> None:
        super().__init__()
        self.severity_threshold = severity_threshold
        s = get_azure_settings()

        self._cs_client: ContentSafetyClient | None = None
        if s.azure_content_safety_endpoint and s.azure_content_safety_key:
            self._cs_client = ContentSafetyClient(
                endpoint=s.azure_content_safety_endpoint,
                credential=AzureKeyCredential(s.azure_content_safety_key),
            )

    def check_input(self, text: str) -> GuardrailResult:
        # 1. Run base rule engine (injection, PII, toxicity keywords)
        base_result = super().check_input(text)
        if not base_result.allowed:
            return base_result

        # 2. Azure Content Safety API
        if self._cs_client:
            try:
                response = self._cs_client.analyze_text(
                    AnalyzeTextOptions(
                        text=text,
                        categories=[
                            TextCategory.HATE,
                            TextCategory.SELF_HARM,
                            TextCategory.SEXUAL,
                            TextCategory.VIOLENCE,
                        ],
                    )
                )
                for result in (response.categories_analysis or []):
                    if result.severity >= self.severity_threshold:
                        return GuardrailResult(
                            allowed=False,
                            reason=f"Azure Content Safety blocked: {result.category} severity {result.severity}",
                            violation_type=ViolationType.TOXIC_CONTENT,
                        )
            except HttpResponseError:
                pass  # Fail open — base engine already ran

        return GuardrailResult(allowed=True, sanitised_text=text)

    def check_output(self, text: str) -> GuardrailResult:
        # Run base PII redaction first
        result = super().check_output(text)
        text_to_check = result.sanitised_text or text

        # Azure Content Safety on output too
        if self._cs_client:
            try:
                response = self._cs_client.analyze_text(
                    AnalyzeTextOptions(
                        text=text_to_check,
                        categories=[TextCategory.HATE, TextCategory.VIOLENCE],
                    )
                )
                for cat in (response.categories_analysis or []):
                    if cat.severity >= self.severity_threshold:
                        return GuardrailResult(
                            allowed=True,
                            reason=f"Output flagged by Azure Content Safety: {cat.category}",
                            violation_type=ViolationType.UNSAFE_OUTPUT,
                            sanitised_text="[Content removed by safety policy]",
                        )
            except HttpResponseError:
                pass

        return result
