#!/usr/bin/env python3
"""Latency SLO gate for CI, with explicit reference-mode stub behavior."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.framework import FrameworkMode, decide_stub, get_framework_mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Check p95 latency SLO")
    parser.add_argument("--p95-threshold", type=float, default=3.0)
    parser.add_argument("--framework-mode", type=FrameworkMode, default=get_framework_mode())
    args = parser.parse_args()

    Path("reports").mkdir(exist_ok=True)
    observed = os.getenv("LLMOPS_OBSERVED_P95_SECONDS")
    if observed:
        p95 = float(observed)
        passed = p95 <= args.p95_threshold
        Path("reports/latency_slo_report.json").write_text(json.dumps({
            "status": "measured",
            "p95_seconds": p95,
            "threshold_seconds": args.p95_threshold,
            "passed": passed,
        }, indent=2))
        sys.exit(0 if passed else 1)

    decision = decide_stub("latency SLO check", args.framework_mode)
    Path("reports/latency_slo_report.json").write_text(json.dumps({
        "status": "stubbed" if decision.allowed else "missing-measurement",
        "framework_mode": args.framework_mode.value,
        "threshold_seconds": args.p95_threshold,
        "allowed": decision.allowed,
        "reason": decision.reason,
    }, indent=2))
    print(decision.reason)
    sys.exit(0 if decision.allowed else 2)


if __name__ == "__main__":
    main()
