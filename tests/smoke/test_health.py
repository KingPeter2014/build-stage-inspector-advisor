"""
tests/smoke/test_health.py
Verify the deployed gateway is up and reports healthy.
"""
import pytest


pytestmark = pytest.mark.smoke


class TestHealth:
    def test_health_endpoint_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}. Body: {response.text}"
        )

    def test_health_response_is_json(self, client):
        response = client.get("/health")
        data = response.json()
        assert isinstance(data, dict)

    def test_health_reports_ok_status(self, client):
        response = client.get("/health")
        data = response.json()
        status = data.get("status", data.get("health", ""))
        assert status in ("ok", "healthy", "UP"), (
            f"Unexpected health status: {data}"
        )

    def test_readiness_endpoint(self, client):
        """
        Some gateways expose /ready or /readyz separately from /health.
        Accept 200 or 404 (not all providers implement this).
        """
        response = client.get("/ready")
        assert response.status_code in (200, 404), (
            f"Unexpected status {response.status_code} from /ready"
        )
