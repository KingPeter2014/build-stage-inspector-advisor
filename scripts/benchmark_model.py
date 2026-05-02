#!/usr/bin/env python3
"""
Model benchmark gate used by model_cicd.yml.

In reference mode this writes a deterministic placeholder report. Production
framework modes require a real benchmark implementation to be supplied for the
project's model registry, datasets, and business metrics.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.framework import FrameworkMode, decide_stub, get_framework_mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark challenger vs champion model")
    parser.add_argument("--challenger", required=True)
    parser.add_argument("--champion", required=True)
    parser.add_argument("--max-regression", type=float, default=0.02)
    parser.add_argument("--framework-mode", type=FrameworkMode, default=get_framework_mode())
    args = parser.parse_args()

    decision = decide_stub("model benchmark", args.framework_mode)
    Path("reports").mkdir(exist_ok=True)

    if decision.allowed:
        Path("reports/benchmark_report.json").write_text(json.dumps({
            "status": "stubbed",
            "framework_mode": args.framework_mode.value,
            "challenger": args.challenger,
            "champion": args.champion,
            "max_regression": args.max_regression,
            "allowed": True,
            "reason": decision.reason,
        }, indent=2))
        print(decision.reason)
        sys.exit(0)

    Path("reports/benchmark_report.json").write_text(json.dumps({
        "status": "missing-implementation",
        "framework_mode": args.framework_mode.value,
        "challenger": args.challenger,
        "champion": args.champion,
        "allowed": False,
        "reason": decision.reason,
    }, indent=2))
    print(decision.reason)
    sys.exit(2)


if __name__ == "__main__":
    main()
