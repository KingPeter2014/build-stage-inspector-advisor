"""
tests/smoke/test_auth.py
Verify that the deployed gateway enforces auth and RBAC correctly.
"""
import pytest


pytestmark = pytest.mark.smoke

_CHAT_PAYLOAD = {
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "ping"}],
    "max_tokens": 5,
}


class TestAuthentication:
    def test_request_with_valid_headers_accepted(self, client):
        """A request with a recognised user role should not return 401 or 403."""
        response = client.post("/v1/chat/completions", json=_CHAT_PAYLOAD)
        assert response.status_code not in (401, 403), (
            f"Valid user got rejected: {response.status_code} — {response.text}"
        )

    def test_request_without_user_id_rejected(self, unauth_client):
        """Requests with no identity headers must be rejected (401 or 403)."""
        response = unauth_client.post("/v1/chat/completions", json=_CHAT_PAYLOAD)
        assert response.status_code in (401, 403), (
            f"Unauthenticated request was not rejected: {response.status_code}"
        )

    def test_viewer_cannot_access_admin_endpoint(self, client):
        """
        The client fixture uses 'developer' role.
        Admin-only endpoints (e.g. /admin/users) should return 403.
        Accept 404 too — not all providers expose admin endpoints.
        """
        response = client.get("/admin/users")
        assert response.status_code in (403, 404), (
            f"Expected 403 or 404 for non-admin on /admin/users, got {response.status_code}"
        )

    def test_admin_can_access_admin_endpoint(self, admin_client):
        """Admin role should not be rejected from admin endpoints (200 or 404 both OK)."""
        response = admin_client.get("/admin/users")
        assert response.status_code in (200, 404), (
            f"Admin was unexpectedly rejected: {response.status_code}"
        )
