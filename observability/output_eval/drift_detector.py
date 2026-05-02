"""
observability/output_eval/drift_detector.py
Detects output drift by comparing embedding distributions of
recent model outputs against a baseline reference window.
Updates Prometheus drift gauge and triggers alerts.
"""
from __future__ import annotations

import json
import numpy as np
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cosine


@dataclass
class DriftReport:
    model: str
    drift_score: float          # 0.0 = no drift, 1.0 = maximum drift
    baseline_size: int
    current_size: int
    computed_at: str
    alert: bool                 # True if drift_score exceeds threshold


class OutputDriftDetector:
    """
    Compares mean embedding centroid of recent outputs (last N hours)
    against a baseline window using cosine distance.
    Simple but effective for production monitoring.
    """

    def __init__(
        self,
        output_log_path: str = "data/output_log.jsonl",
        embedding_model: str = "all-MiniLM-L6-v2",
        baseline_hours: int = 24 * 7,       # 1 week baseline
        current_hours: int = 1,             # Last 1 hour current window
        drift_threshold: float = 0.15,      # Alert threshold
        min_samples: int = 20,
    ):
        self.log_path = Path(output_log_path)
        self.embedder = SentenceTransformer(embedding_model)
        self.baseline_hours = baseline_hours
        self.current_hours = current_hours
        self.drift_threshold = drift_threshold
        self.min_samples = min_samples

    def log_output(self, model: str, output_text: str) -> None:
        """Append a model output to the log for later drift analysis."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "model": model,
            "output": output_text[:500],    # Truncate to save space
        }
        with self.log_path.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def _load_outputs(self, model: str, hours: int, offset_hours: int = 0) -> list[str]:
        if not self.log_path.exists():
            return []
        cutoff = datetime.utcnow() - timedelta(hours=hours + offset_hours)
        end = datetime.utcnow() - timedelta(hours=offset_hours)
        outputs = []
        for line in self.log_path.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("model") != model:
                continue
            ts = datetime.fromisoformat(entry["timestamp"])
            if cutoff <= ts <= end:
                outputs.append(entry["output"])
        return outputs

    def _centroid(self, texts: list[str]) -> np.ndarray:
        embeddings = self.embedder.encode(texts, show_progress_bar=False)
        return embeddings.mean(axis=0)

    def compute_drift(self, model: str) -> DriftReport | None:
        baseline_texts = self._load_outputs(model, self.baseline_hours, offset_hours=self.current_hours)
        current_texts = self._load_outputs(model, self.current_hours)

        if len(baseline_texts) < self.min_samples or len(current_texts) < self.min_samples:
            return None     # Not enough data

        baseline_centroid = self._centroid(baseline_texts)
        current_centroid = self._centroid(current_texts)
        drift_score = float(cosine(baseline_centroid, current_centroid))

        report = DriftReport(
            model=model,
            drift_score=drift_score,
            baseline_size=len(baseline_texts),
            current_size=len(current_texts),
            computed_at=datetime.utcnow().isoformat(),
            alert=drift_score > self.drift_threshold,
        )

        # Update Prometheus gauge
        try:
            from observability.metrics.prometheus_metrics import output_drift_gauge
            output_drift_gauge.labels(model=model).set(drift_score)
        except Exception:
            pass

        return report
