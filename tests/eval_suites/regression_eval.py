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
    """Create a minimal advisor-domain golden dataset if one doesn't exist."""
    samples = [
        EvalSample(
            input="For a new Victorian Class 1 build at pre-start, what should I check?",
            expected_output=(
                "Check contract scope, permit documents, approved plans, inspection "
                "requirements, and the applicable 7-star energy compliance pathway."
            ),
            actual_output="",   # Filled at eval time
        ),
        EvalSample(
            input="For bathroom waterproofing in a Victorian Class 1 home, what should the advisor look for under NCC DTS?",
            expected_output=(
                "Check NCC wet-area waterproofing evidence, AS 3740 references, penetrations, "
                "junctions, floor wastes, and inspection records."
            ),
            actual_output="",
        ),
        EvalSample(
            input="At frame stage, can the advisor certify structural safety from a builder message alone?",
            expected_output=(
                "No. The advisor should not certify structural safety and should require "
                "building surveyor or engineering evidence."
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
    parser = argparse.ArgumentParser(description="Build Stage Inspector Advisor regression eval suite")
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

    print("\n── Eval Report ──────────────────────────────")
    print(f"  Total:     {report.total}")
    print(f"  Passed:    {report.passed}")
    print(f"  Failed:    {report.failed}")
    print(f"  Pass rate: {report.pass_rate:.1%}")
    print(f"  Gate:      {'✅ PASS' if report.is_gate_passing(args.min_pass_rate) else '❌ FAIL'}")
    print(f"  Metrics:   {report.metric_scores}")

    if not report.is_gate_passing(args.min_pass_rate):
        print("\nFailed cases:")
        for failure in report.failures[:3]:
            print(f"  Input: {failure['input'][:80]}...")
        sys.exit(1)

    print("\nEval gate passed ✅")
    sys.exit(0)


if __name__ == "__main__":
    main()
