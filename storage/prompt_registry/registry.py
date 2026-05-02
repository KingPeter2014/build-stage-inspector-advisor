"""
storage/prompt_registry/registry.py
Versioned prompt registry backed by Langfuse (or local JSON fallback).
Prompts are first-class versioned artefacts — not hardcoded strings.
"""
from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class PromptVersion:
    name: str
    version: int
    template: str                           # Jinja2-style: "Answer: {{ question }}"
    model: str = "gpt-4o"
    parameters: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    hash: str = ""                          # SHA-256 of template — auto-set on __post_init__

    def __post_init__(self):
        self.hash = hashlib.sha256(self.template.encode()).hexdigest()[:12]

    def render(self, **variables) -> str:
        """Simple variable substitution — swap for Jinja2 where needed."""
        result = self.template
        for key, value in variables.items():
            result = result.replace("{{ " + key + " }}", str(value))
            result = result.replace("{{" + key + "}}", str(value))
        return result


class LocalPromptRegistry:
    """
    File-backed prompt registry for development.
    In production, swap this for LangfusePromptRegistry (see below).
    """

    def __init__(self, registry_path: str = "storage/prompt_registry/prompts.json"):
        self.path = Path(registry_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._store: dict[str, list[dict]] = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            return json.loads(self.path.read_text())
        return {}

    def _save(self) -> None:
        self.path.write_text(json.dumps(self._store, indent=2))

    def push(self, prompt: PromptVersion) -> PromptVersion:
        """Register a new version (auto-increments version number)."""
        versions = self._store.get(prompt.name, [])
        prompt.version = len(versions) + 1
        versions.append(asdict(prompt))
        self._store[prompt.name] = versions
        self._save()
        return prompt

    def get(self, name: str, version: int | None = None) -> PromptVersion:
        """Retrieve a prompt by name; latest version if version is None."""
        versions = self._store.get(name)
        if not versions:
            raise KeyError(f"Prompt '{name}' not found in registry")
        data = versions[-1] if version is None else versions[version - 1]
        return PromptVersion(**data)

    def list_prompts(self) -> list[str]:
        return list(self._store.keys())

    def list_versions(self, name: str) -> list[PromptVersion]:
        return [PromptVersion(**v) for v in self._store.get(name, [])]


class LangfusePromptRegistry:
    """Production registry backed by Langfuse."""

    def __init__(self, public_key: str, secret_key: str, host: str):
        from langfuse import Langfuse
        self.client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)

    def push(self, prompt: PromptVersion) -> PromptVersion:
        self.client.create_prompt(
            name=prompt.name,
            prompt=prompt.template,
            config=prompt.parameters,
            labels=prompt.tags,
        )
        return prompt

    def get(self, name: str, version: int | None = None) -> PromptVersion:
        p = self.client.get_prompt(name, version=version)
        return PromptVersion(name=name, version=version or 0, template=p.prompt)
