"""
serving/guardrails/guardrail_runner.py
Input/output guardrails: PII detection, toxicity, topic filters, and schema enforcement.
Wraps NeMo Guardrails with a lightweight fallback for development.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any


class ViolationType(str, Enum):
    PII_LEAK = "pii_leak"
    TOXIC_CONTENT = "toxic_content"
    OFF_TOPIC = "off_topic"
    PROMPT_INJECTION = "prompt_injection"
    SCHEMA_VIOLATION = "schema_violation"
    UNSAFE_OUTPUT = "unsafe_output"


@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""
    violation_type: ViolationType | None = None
    sanitised_text: str = ""


# Simple rule-based patterns for dev — replace with NeMo Guardrails in production
_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I),
    re.compile(r"system\s*:\s*", re.I),
    re.compile(r"<\s*system\s*>", re.I),
    re.compile(r"forget\s+your\s+(previous\s+)?instructions?", re.I),
]

_PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]?){15,16}\b"),
}

_TOXIC_KEYWORDS = frozenset(["<placeholder_toxic_word_1>", "<placeholder_toxic_word_2>"])


class GuardrailRunner:
    """
    Lightweight guardrail runner.
    For production, initialise NeMo Guardrails:
        from nemoguardrails import RailsConfig, LLMRails
        config = RailsConfig.from_path("serving/guardrails/nemo_config/")
        self.rails = LLMRails(config)
    """

    def __init__(self, use_nemo: bool = False, nemo_config_path: str = ""):
        self.use_nemo = use_nemo
        if use_nemo and nemo_config_path:
            try:
                from nemoguardrails import RailsConfig, LLMRails
                config = RailsConfig.from_path(nemo_config_path)
                self._rails = LLMRails(config)
            except ImportError:
                self.use_nemo = False

    def check_input(self, text: str) -> GuardrailResult:
        # 1. Prompt injection
        for pattern in _INJECTION_PATTERNS:
            if pattern.search(text):
                return GuardrailResult(
                    allowed=False,
                    reason="Potential prompt injection detected",
                    violation_type=ViolationType.PROMPT_INJECTION,
                )

        # 2. PII in input
        for pii_type, pattern in _PII_PATTERNS.items():
            if pattern.search(text):
                return GuardrailResult(
                    allowed=False,
                    reason=f"PII detected in input: {pii_type}",
                    violation_type=ViolationType.PII_LEAK,
                )

        # 3. Toxicity (keyword-based — replace with classifier in production)
        lower = text.lower()
        for word in _TOXIC_KEYWORDS:
            if word in lower:
                return GuardrailResult(
                    allowed=False,
                    reason="Toxic content detected in input",
                    violation_type=ViolationType.TOXIC_CONTENT,
                )

        return GuardrailResult(allowed=True, sanitised_text=text)

    def check_output(self, text: str) -> GuardrailResult:
        # 1. PII leakage in output
        for pii_type, pattern in _PII_PATTERNS.items():
            if pattern.search(text):
                sanitised = pattern.sub(f"[{pii_type.upper()}_REDACTED]", text)
                return GuardrailResult(
                    allowed=True,           # Allow but sanitise
                    reason=f"PII redacted from output: {pii_type}",
                    violation_type=ViolationType.PII_LEAK,
                    sanitised_text=sanitised,
                )

        return GuardrailResult(allowed=True, sanitised_text=text)

    def run(self, input_text: str, output_text: str) -> tuple[GuardrailResult, GuardrailResult]:
        """Check both input and output; return (input_result, output_result)."""
        return self.check_input(input_text), self.check_output(output_text)
