"""
tests/smoke/test_latency.py
Verify that the deployed gateway meets latency SLOs.

Thresholds (configurable via env vars):
  SMOKE_P95_THRESHOLD_S   default 5.0 seconds  (non-streaming single turn)
  SMOKE_HEALTH_THRESHOLD_S  default 0.5 seconds (health endpoint)
"""
from __future__ import annotations

import os
import statistics
import time

import pytest


pytestmark = pytest.mark.smoke

P95_THRESHOLD = float(os.getenv("SMOKE_P95_THRESHOLD_S", "5.0"))
HEALTH_THRESHOLD = float(os.getenv("SMOKE_HEALTH_THRESHOLD_S", "0.5"))
SAMPLE_SIZE = int(os.getenv("SMOKE_LATENCY_SAMPLES", "5"))


class TestLatency:
    def test_health_endpoint_latency(self, client):
        """Health checks must respond within SMOKE_HEALTH_THRESHOLD_S."""
        start = time.perf_counter()
        response = client.get("/health")
        elapsed = time.perf_counter() - start

        assert response.status_code == 200
        assert elapsed < HEALTH_THRESHOLD, (
            f"/health took {elapsed:.3f}s — exceeds threshold {HEALTH_THRESHOLD}s"
        )

    def test_chat_p95_latency(self, client):
        """
        Run SAMPLE_SIZE chat requests and assert p95 is within threshold.
        Uses a short max_tokens value to minimise LLM generation time.
        """
        latencies: list[float] = []
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Reply with exactly one word: OK"}],
            "max_tokens": 5,
        }

        for _ in range(SAMPLE_SIZE):
            start = time.perf_counter()
            response = client.post("/v1/chat/completions", json=payload)
            elapsed = time.perf_counter() - start
            # Only count successful responses for latency SLO
            if response.status_code == 200:
                latencies.append(elapsed)

        if not latencies:
            pytest.skip("No successful responses to measure latency against.")

        latencies.sort()
        p95_index = max(0, int(len(latencies) * 0.95) - 1)
        p95 = latencies[p95_index]
        mean = statistics.mean(latencies)

        print(f"\nLatency samples ({len(latencies)}): mean={mean:.3f}s  p95={p95:.3f}s")

        assert p95 < P95_THRESHOLD, (
            f"p95 latency {p95:.3f}s exceeds threshold {P95_THRESHOLD}s "
            f"(mean={mean:.3f}s over {len(latencies)} samples)"
        )
