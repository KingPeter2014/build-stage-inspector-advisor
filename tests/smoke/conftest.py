"""
tests/smoke/conftest.py
Fixtures shared across all smoke tests.
All smoke tests are auto-skipped when GATEWAY_URL is not set (handled by root conftest).
"""
from __future__ import annotations

import os
import pytest
import httpx


@pytest.fixture(scope="session")
def client(gateway_url: str) -> httpx.Client:
    """Synchronous HTTP client pointed at the deployed gateway."""
    headers = {
        "X-User-Id": os.getenv("X_USER_ID", "smoke-test-user"),
        "X-User-Role": os.getenv("X_USER_ROLE", "developer"),
        "X-Team-Id": os.getenv("X_TEAM_ID", "smoke-team"),
    }
    with httpx.Client(base_url=gateway_url, headers=headers, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def admin_client(gateway_url: str) -> httpx.Client:
    """Client with admin role — for testing permission boundaries."""
    headers = {
        "X-User-Id": "smoke-admin",
        "X-User-Role": "admin",
        "X-Team-Id": "smoke-team",
    }
    with httpx.Client(base_url=gateway_url, headers=headers, timeout=30.0) as c:
        yield c


@pytest.fixture(scope="session")
def unauth_client(gateway_url: str) -> httpx.Client:
    """Client with no auth headers — for testing rejection of unauthenticated requests."""
    with httpx.Client(base_url=gateway_url, timeout=10.0) as c:
        yield c
