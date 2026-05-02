"""
observability/feedback/collector.py
Collects user feedback signals and routes them to:
  1. Langfuse (for observability dashboards)
  2. A retraining queue (JSONL file or Kafka topic)
These become new eval cases and fine-tuning candidates.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path


class FeedbackSignal(str, Enum):
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    FLAGGED = "flagged"           # Safety / policy concern
    CORRECTED = "corrected"       # User provided a correction


@dataclass
class FeedbackEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trace_id: str = ""                  # Links to OpenTelemetry span
    question: str = ""
    model_output: str = ""
    signal: FeedbackSignal = FeedbackSignal.THUMBS_UP
    correction: str | None = None       # User-provided correct answer
    user_id: str = "anonymous"
    model: str = ""
    prompt_version: int = 0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class FeedbackCollector:
    def __init__(
        self,
        queue_path: str = "data/feedback_queue.jsonl",
        langfuse_enabled: bool = False,
    ):
        self.queue_path = Path(queue_path)
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        self.langfuse_enabled = langfuse_enabled
        self._langfuse = None

        if langfuse_enabled:
            try:
                from langfuse import Langfuse
                from config.settings import get_settings
                s = get_settings()
                self._langfuse = Langfuse(
                    public_key=s.langfuse_public_key,
                    secret_key=s.langfuse_secret_key,
                    host=s.langfuse_host,
                )
            except Exception:
                pass

    def record(self, entry: FeedbackEntry) -> None:
        """Persist feedback to the queue and optionally to Langfuse."""
        # Always write to local queue (durable)
        with self.queue_path.open("a") as f:
            f.write(json.dumps(asdict(entry)) + "\n")

        # Push to Langfuse if configured
        if self._langfuse and entry.trace_id:
            self._langfuse.score(
                trace_id=entry.trace_id,
                name=entry.signal.value,
                value=1.0 if entry.signal == FeedbackSignal.THUMBS_UP else 0.0,
                comment=entry.correction,
            )

    def drain_to_eval_dataset(self, output_path: str, signals: list[FeedbackSignal] | None = None) -> int:
        """
        Convert queued feedback into an eval dataset (JSONL).
        Returns number of samples exported.
        Only exports entries with corrections (thumbs_down + correction).
        """
        if not self.queue_path.exists():
            return 0

        target_signals = signals or [FeedbackSignal.THUMBS_DOWN, FeedbackSignal.CORRECTED]
        exported = 0

        with open(output_path, "a") as out:
            for line in self.queue_path.read_text().splitlines():
                entry_data = json.loads(line)
                if entry_data.get("signal") in [s.value for s in target_signals]:
                    if entry_data.get("correction"):
                        eval_sample = {
                            "input": entry_data["question"],
                            "expected_output": entry_data["correction"],
                            "actual_output": entry_data["model_output"],
                            "metadata": {
                                "source": "user_feedback",
                                "feedback_id": entry_data["id"],
                            },
                        }
                        out.write(json.dumps(eval_sample) + "\n")
                        exported += 1

        return exported
