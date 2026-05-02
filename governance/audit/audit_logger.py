"""
governance/audit/audit_logger.py
Tamper-evident audit logger for SOC 2 / HIPAA / GDPR compliance.
Every LLM interaction is logged with full context, hashed for integrity.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class AuditEntry:
    """Immutable audit record for one LLM interaction."""
    audit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    # Who
    user_id: str = "anonymous"
    team_id: str = "default"
    ip_address: str = ""

    # What
    action: str = ""                # e.g. "chat_completion", "rag_query", "fine_tune"
    model: str = ""
    prompt_version: int = 0
    trace_id: str = ""

    # Input / output (store hashes only in high-sensitivity environments)
    input_hash: str = ""            # SHA-256 of full input
    output_hash: str = ""           # SHA-256 of full output
    input_preview: str = ""         # First 200 chars (redact for PHI)
    output_preview: str = ""

    # Cost & tokens
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0

    # PII / safety flags
    pii_detected: bool = False
    guardrail_triggered: bool = False
    guardrail_type: str = ""

    # Integrity
    entry_hash: str = ""            # SHA-256 of the rest of the record — set last

    def finalise(self) -> "AuditEntry":
        """Compute the integrity hash over all other fields."""
        data = asdict(self)
        data.pop("entry_hash")
        canonical = json.dumps(data, sort_keys=True)
        self.entry_hash = hashlib.sha256(canonical.encode()).hexdigest()
        return self

    def verify(self) -> bool:
        """Verify this entry has not been tampered with."""
        data = asdict(self)
        stored_hash = data.pop("entry_hash")
        canonical = json.dumps(data, sort_keys=True)
        return hashlib.sha256(canonical.encode()).hexdigest() == stored_hash


@dataclass
class AuditConfig:
    log_path: str = "data/audit/audit.jsonl"
    store_full_content: bool = False    # Set False for HIPAA environments
    redact_pii: bool = True
    retention_days: int = 365           # HIPAA minimum: 6 years


class AuditLogger:
    def __init__(self, config: AuditConfig | None = None):
        self.config = config or AuditConfig()
        self.log_path = Path(self.config.log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def log(
        self,
        action: str,
        model: str,
        input_text: str,
        output_text: str,
        user_id: str = "anonymous",
        team_id: str = "default",
        **kwargs: Any,
    ) -> AuditEntry:
        entry = AuditEntry(
            action=action,
            model=model,
            user_id=user_id,
            team_id=team_id,
            input_hash=self._hash(input_text),
            output_hash=self._hash(output_text),
            input_preview=input_text[:200] if not self.config.redact_pii else "[REDACTED]",
            output_preview=output_text[:200],
            **{k: v for k, v in kwargs.items() if hasattr(AuditEntry, k)},
        )
        entry.finalise()

        with self.log_path.open("a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

        return entry

    def verify_log_integrity(self) -> tuple[int, int]:
        """Returns (valid_count, tampered_count)."""
        valid = tampered = 0
        for line in self.log_path.read_text().splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            entry = AuditEntry(**data)
            if entry.verify():
                valid += 1
            else:
                tampered += 1
        return valid, tampered
