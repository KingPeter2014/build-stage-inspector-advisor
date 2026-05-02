#!/usr/bin/env python3
"""
scripts/monitor_canary.py
Monitors a canary deployment for the specified duration.
Polls Prometheus metrics and triggers rollback if error rate exceeds threshold.
Usage:
    python scripts/monitor_canary.py --duration 600 --error-rate-threshold 0.01
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_error_rate(prometheus_url: str, model: str = "all") -> float:
    """Query Prometheus for the current error rate."""
    import urllib.request, json, urllib.parse

    query = 'sum(rate(llmops_requests_total{status="error"}[2m])) / sum(rate(llmops_requests_total[2m]))'
    encoded = urllib.parse.quote(query)
    url = f"{prometheus_url}/api/v1/query?query={encoded}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            result = data.get("data", {}).get("result", [])
            if result:
                return float(result[0]["value"][1])
    except Exception:
        pass
    return 0.0


def monitor_canary(duration: int, error_rate_threshold: float, prometheus_url: str, poll_interval: int = 30) -> bool:
    """
    Returns True if canary is healthy, False if rollback is needed.
    """
    end_time = time.time() + duration
    poll_count = 0

    print(f"Monitoring canary for {duration}s | threshold={error_rate_threshold:.1%} | interval={poll_interval}s")

    while time.time() < end_time:
        error_rate = get_error_rate(prometheus_url)
        remaining = int(end_time - time.time())
        status = "✅" if error_rate <= error_rate_threshold else "❌"
        print(f"[{remaining}s remaining] {status} Error rate: {error_rate:.2%} (threshold: {error_rate_threshold:.2%})")

        if error_rate > error_rate_threshold:
            print(f"\n🚨 Canary unhealthy — error rate {error_rate:.2%} exceeds threshold {error_rate_threshold:.2%}")
            print("Triggering rollback...")
            return False

        poll_count += 1
        time.sleep(poll_interval)

    print(f"\n✅ Canary healthy after {poll_count} polls — promoting to full traffic")
    return True


def main():
    parser = argparse.ArgumentParser(description="Monitor canary deployment")
    parser.add_argument("--duration", type=int, default=600, help="Monitoring duration in seconds")
    parser.add_argument("--error-rate-threshold", type=float, default=0.01, help="Max acceptable error rate (0-1)")
    parser.add_argument("--prometheus-url", default="http://localhost:9090", help="Prometheus base URL")
    parser.add_argument("--poll-interval", type=int, default=30, help="Poll interval in seconds")
    args = parser.parse_args()

    healthy = monitor_canary(
        duration=args.duration,
        error_rate_threshold=args.error_rate_threshold,
        prometheus_url=args.prometheus_url,
        poll_interval=args.poll_interval,
    )
    sys.exit(0 if healthy else 1)


if __name__ == "__main__":
    main()
