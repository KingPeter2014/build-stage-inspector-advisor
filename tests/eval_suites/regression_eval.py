"""
tests/eval_suites/regression_eval.py
Regression eval suite run as a CI gate.
Loads the golden dataset and runs the LLMEvaluator.
Exit code 0 = pass, 1 = fail (used by GitHub Actions gate).
"""
import argparse
import json
import sys
from pathlib import Path

from model_development.evaluation.eval_harness import (
    GoldenDataset,
    LLMEvaluator,
    EvalSample,
)


GOLDEN_DATASET_PATH = "data/eval_datasets/regression_golden.jsonl"
REPORT_PATH = "reports/eval_report.json"


def seed_golden_dataset() -> None:
    """Create a minimal golden dataset if one doesn't exist."""
    samples = [
        EvalSample(
            input="What is retrieval-augmented generation?",
            expected_output=(
                "RAG is a technique that combines a retrieval system with a generative "
                "model. It fetches relevant documents from a knowledge base and uses them "
                "as context for generating accurate, grounded responses."
            ),
            actual_output="",   # Filled at eval time
        ),
        EvalSample(
            input="Name three key components of LLMOps.",
            expected_output=(
                "Three key components are: data ingestion pipelines, model evaluation frameworks, "
                "and observability tooling including distributed tracing and metrics."
            ),
            actual_output="",
        ),
        EvalSample(
            input="What is the purpose of a prompt registry?",
            expected_output=(
                "A prompt registry stores and versions prompts as first-class artefacts, "
                "allowing teams to track changes, roll back regressions, and deploy prompts "
                "through CI/CD pipelines."
            ),
            actual_output="",
        ),
        EvalSample(
            input="Why is a golden dataset important in LLM CI/CD?",
            expected_output=(
                "A golden dataset provides a curated set of input/expected-output pairs "
                "that serve as regression tests. It catches prompt or model regressions "
                "before they reach production."
            ),
            actual_output="",
        ),
        EvalSample(
            input="What does the champion/challenger pattern mean in model deployment?",
            expected_output=(
                "The champion is the current production model. A challenger is a new candidate "
                "model that runs in parallel receiving a small slice of traffic. Metrics are "
                "compared before the challenger is promoted to replace the champion."
            ),
            actual_output="",
        ),
    ]
    Path(GOLDEN_DATASET_PATH).parent.mkdir(parents=True, exist_ok=True)
    GoldenDataset.save(samples, GOLDEN_DATASET_PATH)
    print(f"Seeded {len(samples)} samples → {GOLDEN_DATASET_PATH}")


def fill_actual_outputs(samples: list[EvalSample], model: str) -> list[EvalSample]:
    """Run the production gateway/model to fill actual_output for each sample."""
    import litellm
    filled = []
    for sample in samples:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": sample.input}],
            max_tokens=512,
        )
        sample.actual_output = response.choices[0].message.content
        filled.append(sample)
    return filled


def main():
    parser = argparse.ArgumentParser(description="LLMOps regression eval suite")
    parser.add_argument("--model", default="gpt-4o", help="Model to evaluate")
    parser.add_argument("--min-pass-rate", type=float, default=0.90, help="Minimum pass rate gate")
    parser.add_argument("--seed", action="store_true", help="Seed the golden dataset if missing")
    args = parser.parse_args()

    if args.seed or not Path(GOLDEN_DATASET_PATH).exists():
        seed_golden_dataset()

    samples = GoldenDataset.load(GOLDEN_DATASET_PATH)
    print(f"Loaded {len(samples)} samples from golden dataset")

    print("Filling actual outputs via model inference...")
    samples = fill_actual_outputs(samples, model=args.model)

    print("Running evaluation metrics...")
    evaluator = LLMEvaluator(model=args.model)
    report = evaluator.run(samples)

    Path(REPORT_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(REPORT_PATH).write_text(json.dumps(report.to_dict(), indent=2))

    print(f"\n── Eval Report ──────────────────────────────")
    print(f"  Total:     {report.total}")
    print(f"  Passed:    {report.passed}")
    print(f"  Failed:    {report.failed}")
    print(f"  Pass rate: {report.pass_rate:.1%}")
    print(f"  Gate:      {'✅ PASS' if report.is_gate_passing(args.min_pass_rate) else '❌ FAIL'}")
    print(f"  Metrics:   {report.metric_scores}")

    if not report.is_gate_passing(args.min_pass_rate):
        print(f"\nFailed cases:")
        for failure in report.failures[:3]:
            print(f"  Input: {failure['input'][:80]}...")
        sys.exit(1)

    print("\nEval gate passed ✅")
    sys.exit(0)


if __name__ == "__main__":
    main()
