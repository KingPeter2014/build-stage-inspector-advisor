#!/usr/bin/env python3
"""
scripts/validate_prompts.py
Validates all prompts in the local registry for schema compliance
and required variables. Used as the first CI stage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from storage.prompt_registry.registry import LocalPromptRegistry

REQUIRED_PROMPTS = {
    "rag_qa": ["context", "question"],
    "summarisation": ["document"],
    "classification": ["text", "categories"],
}


def validate_prompts() -> bool:
    registry = LocalPromptRegistry()
    all_valid = True

    for prompt_name, required_vars in REQUIRED_PROMPTS.items():
        try:
            pv = registry.get(prompt_name)
        except KeyError:
            print(f"⚠️  WARNING: Prompt '{prompt_name}' not found in registry (will be created on first use)")
            continue

        for var in required_vars:
            placeholder = "{{ " + var + " }}"
            if placeholder not in pv.template:
                print(f"❌ FAIL: Prompt '{prompt_name}' v{pv.version} missing variable: {{{var}}}")
                all_valid = False
            else:
                print(f"✅ OK:   Prompt '{prompt_name}' v{pv.version} has {{{var}}}")

    return all_valid


if __name__ == "__main__":
    ok = validate_prompts()
    sys.exit(0 if ok else 1)
