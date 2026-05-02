"""
core/schemas/evaluation.py
Canonical evaluation result models shared across all provider eval harnesses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EvalMetrics:
    faithfulness: float = 0.0          # How factually grounded is the answer
    answer_relevancy: float = 0.0      # How relevant is the answer to the question
    context_recall: float = 0.0        # Did retrieval capture needed context
    context_precision: float = 0.0     # Is the retrieved context on-topic
    correctness: float = 0.0           # Ground-truth correctness (for regression)
    latency_p50_ms: float = 0.0
    latency_p95_ms: float = 0.0


@dataclass
class EvalResult:
    suite: str
    model: str
    provider: str
    run_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    metrics: EvalMetrics = field(default_factory=EvalMetrics)
    passed: bool = False
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: list[dict] = field(default_factory=list)
    notes: str = ""
