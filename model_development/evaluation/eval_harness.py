"""
model_development/evaluation/eval_harness.py
Evaluation harness for LLM outputs — supports golden datasets,
DeepEval metrics, and Ragas RAG metrics.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from deepeval import evaluate
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    HallucinationMetric,
    GEval,
)
from deepeval.test_case import LLMTestCase


@dataclass
class EvalSample:
    input: str
    expected_output: str
    actual_output: str = ""
    retrieval_context: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvalReport:
    total: int
    passed: int
    failed: int
    pass_rate: float
    metric_scores: dict[str, float]
    failures: list[dict[str, Any]]

    def is_gate_passing(self, min_pass_rate: float = 0.90) -> bool:
        return self.pass_rate >= min_pass_rate

    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "metric_scores": self.metric_scores,
            "gate_passing": self.is_gate_passing(),
        }


class GoldenDataset:
    """Load/save eval samples from JSONL files."""

    @staticmethod
    def load(path: str) -> list[EvalSample]:
        samples = []
        for line in Path(path).read_text().splitlines():
            if line.strip():
                samples.append(EvalSample(**json.loads(line)))
        return samples

    @staticmethod
    def save(samples: list[EvalSample], path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for s in samples:
                f.write(json.dumps(s.__dict__) + "\n")


class LLMEvaluator:
    """
    Runs a suite of DeepEval metrics against a golden dataset.
    Use this as the CI/CD eval gate.
    """

    def __init__(self, model: str = "gpt-4o", threshold: float = 0.7):
        self.model = model
        self.threshold = threshold
        self.metrics = [
            AnswerRelevancyMetric(threshold=threshold, model=model),
            HallucinationMetric(threshold=threshold, model=model),
            FaithfulnessMetric(threshold=threshold, model=model),
        ]

    def run(self, samples: list[EvalSample]) -> EvalReport:
        test_cases = [
            LLMTestCase(
                input=s.input,
                expected_output=s.expected_output,
                actual_output=s.actual_output,
                retrieval_context=s.retrieval_context or None,
            )
            for s in samples
        ]

        results = evaluate(test_cases, self.metrics)

        passed = sum(1 for r in results.test_results if r.success)
        failed_cases = [
            {"input": tc.input, "reason": r.metrics_data}
            for tc, r in zip(test_cases, results.test_results)
            if not r.success
        ]

        # Aggregate mean scores per metric
        metric_scores: dict[str, list[float]] = {}
        for r in results.test_results:
            for m in r.metrics_data:
                metric_scores.setdefault(m.name, []).append(m.score or 0.0)

        return EvalReport(
            total=len(samples),
            passed=passed,
            failed=len(samples) - passed,
            pass_rate=passed / max(len(samples), 1),
            metric_scores={k: sum(v) / len(v) for k, v in metric_scores.items()},
            failures=failed_cases,
        )


class RAGEvaluator:
    """Ragas-based evaluation for RAG pipelines."""

    def run(self, samples: list[EvalSample]) -> dict[str, float]:
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import answer_relevancy, faithfulness, context_recall
        from datasets import Dataset

        data = {
            "question": [s.input for s in samples],
            "answer": [s.actual_output for s in samples],
            "contexts": [s.retrieval_context for s in samples],
            "ground_truth": [s.expected_output for s in samples],
        }
        dataset = Dataset.from_dict(data)
        result = ragas_evaluate(dataset, metrics=[answer_relevancy, faithfulness, context_recall])
        return dict(result)
