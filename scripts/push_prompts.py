#!/usr/bin/env python3
"""
scripts/push_prompts.py
Promotes all prompts from the local registry to Langfuse (production).
Run after eval gates pass on main branch.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from storage.prompt_registry.registry import LocalPromptRegistry, LangfusePromptRegistry


def push_prompts(env: str) -> None:
    settings = get_settings()
    local = LocalPromptRegistry()

    if env == "production":
        if not settings.langfuse_public_key:
            print("❌ LANGFUSE_PUBLIC_KEY not set — cannot push to production registry")
            sys.exit(1)
        remote = LangfusePromptRegistry(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
    else:
        print(f"ℹ️  env={env}: using local registry (no remote push)")
        remote = local

    prompts = local.list_prompts()
    print(f"Found {len(prompts)} prompts in local registry")

    for name in prompts:
        latest = local.get(name)
        try:
            remote.push(latest)
            print(f"✅ Pushed: {name} v{latest.version} (hash={latest.hash})")
        except Exception as e:
            print(f"❌ Failed: {name} — {e}")
            sys.exit(1)

    print(f"\nAll {len(prompts)} prompts pushed to {env} registry ✅")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default="development", choices=["development", "staging", "production"])
    args = parser.parse_args()
    push_prompts(args.env)
