"""
observability/metrics/prometheus_metrics.py
Prometheus metrics for the LLMOps serving layer.
Exposes: request counts, token usage, latency, cost, and drift indicators.
"""
from prometheus_client import Counter, Histogram, Gauge, start_http_server

# ── Request counters ───────────────────────────────────────────────────────────
request_counter = Counter(
    "llmops_requests_total",
    "Total LLM requests",
    ["model", "team", "status"],
)

# ── Token usage ────────────────────────────────────────────────────────────────
token_counter = Counter(
    "llmops_tokens_total",
    "Total tokens consumed",
    ["model", "token_type"],  # token_type: prompt | completion
)

# ── Latency ────────────────────────────────────────────────────────────────────
latency_histogram = Histogram(
    "llmops_request_latency_seconds",
    "Request latency in seconds",
    ["model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# ── TTFT (time to first token) for streaming ──────────────────────────────────
ttft_histogram = Histogram(
    "llmops_ttft_seconds",
    "Time to first token for streaming requests",
    ["model"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

# ── Cost tracking ──────────────────────────────────────────────────────────────
cost_counter = Counter(
    "llmops_cost_usd_total",
    "Estimated total cost in USD",
    ["model", "team"],
)

# ── RAG quality gauges (updated by eval jobs) ─────────────────────────────────
rag_faithfulness_gauge = Gauge(
    "llmops_rag_faithfulness",
    "Rolling mean faithfulness score from eval pipeline",
    ["model"],
)

rag_answer_relevancy_gauge = Gauge(
    "llmops_rag_answer_relevancy",
    "Rolling mean answer relevancy score",
    ["model"],
)

# ── Guardrail violations ───────────────────────────────────────────────────────
guardrail_violations_counter = Counter(
    "llmops_guardrail_violations_total",
    "Number of guardrail violations triggered",
    ["violation_type", "model"],
)

# ── Drift indicator ────────────────────────────────────────────────────────────
output_drift_gauge = Gauge(
    "llmops_output_drift_score",
    "Output drift score vs. baseline (0 = no drift, 1 = high drift)",
    ["model"],
)


def start_metrics_server(port: int = 8000) -> None:
    """Start the Prometheus scrape endpoint."""
    start_http_server(port)
    print(f"Prometheus metrics server started on :{port}")
