#!/usr/bin/env python3
"""Register or promote a model version, with reference-mode stub behavior."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.framework import FrameworkMode, decide_stub, get_framework_mode


def main() -> None:
    parser = argparse.ArgumentParser(description="Register model in the configured registry")
    parser.add_argument("--stage", default="Production")
    parser.add_argument("--model-name", default="llmops-model")
    parser.add_argument("--version", default="latest")
    parser.add_argument("--framework-mode", type=FrameworkMode, default=get_framework_mode())
    args = parser.parse_args()

    decision = decide_stub("model registry promotion", args.framework_mode)
    Path("reports").mkdir(exist_ok=True)
    Path("reports/model_registration_report.json").write_text(json.dumps({
        "status": "stubbed" if decision.allowed else "missing-implementation",
        "framework_mode": args.framework_mode.value,
        "model_name": args.model_name,
        "version": args.version,
        "stage": args.stage,
        "allowed": decision.allowed,
        "reason": decision.reason,
    }, indent=2))
    print(decision.reason)
    sys.exit(0 if decision.allowed else 2)


if __name__ == "__main__":
    main()
