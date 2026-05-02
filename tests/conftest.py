"""
tests/conftest.py
Root conftest — environment detection, shared fixtures, and automatic skip logic.

Existing tests are unaffected: none of the new fixtures are required by existing
test classes. The skip hooks only fire for tests that carry the new markers.

Environment tiers
-----------------
  development  Local dev machine. No cloud credentials expected. Services via
               docker-compose.test.yml. Set APP_ENV=development (default).
  staging      Shared cloud environment. Cloud credentials available via GitHub
               Environment secrets. Set APP_ENV=staging.
  production   Live cloud. Never auto-deployed; requires explicit promotion
               workflow. Set APP_ENV=production.

Controlling test execution
--------------------------
  pytest                         # unit tests only (default addopts filter)
  pytest -m integration          # integration tests (needs docker-compose.test.yml)
  pytest -m smoke                # smoke tests (needs GATEWAY_URL)
  pytest -m requires_cloud       # cloud tests (needs LLMOPS_RUN_CLOUD_TESTS=1)
  pytest -m "unit or integration" # combined
"""
from __future__ import annotations

import os
import socket
import time

import pytest


# ── Environment detection ──────────────────────────────────────────────────────

APP_ENV = os.getenv("APP_ENV", "development")
RUN_CLOUD_TESTS = os.getenv("LLMOPS_RUN_CLOUD_TESTS", "").lower() in ("1", "true", "yes")
LOCALSTACK_URL = os.getenv("LLMOPS_LOCALSTACK_URL", "")
GATEWAY_URL = os.getenv("GATEWAY_URL", "")


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return True if a TCP port is accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ── Automatic skip hooks ───────────────────────────────────────────────────────

def pytest_collection_modifyitems(config, items):
    """
    Inspect each collected test item and attach a skip marker when its
    environment prerequisites are not satisfied.  This runs AFTER collection
    so the existing -m filter in addopts still applies first.
    """
    for item in items:
        # requires_cloud → skip unless LLMOPS_RUN_CLOUD_TESTS=1
        if item.get_closest_marker("requires_cloud") and not RUN_CLOUD_TESTS:
            item.add_marker(
                pytest.mark.skip(
                    reason="Cloud tests disabled. Set LLMOPS_RUN_CLOUD_TESTS=1 to enable."
                )
            )

        # requires_localstack → skip unless LocalStack URL is set and reachable
        if item.get_closest_marker("requires_localstack"):
            if not LOCALSTACK_URL:
                item.add_marker(
                    pytest.mark.skip(
                        reason="LocalStack not configured. Set LLMOPS_LOCALSTACK_URL (e.g. http://localhost:4566)."
                    )
                )
            else:
                # Quick reachability check (parse host:port from URL)
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(LOCALSTACK_URL)
                    host = parsed.hostname or "localhost"
                    port = parsed.port or 4566
                    if not _port_open(host, port):
                        item.add_marker(
                            pytest.mark.skip(
                                reason=f"LocalStack not reachable at {LOCALSTACK_URL}. "
                                       "Run: docker compose -f docker-compose.test.yml up -d"
                            )
                        )
                except Exception:
                    pass

        # smoke → skip unless GATEWAY_URL is set
        if item.get_closest_marker("smoke") and not GATEWAY_URL:
            item.add_marker(
                pytest.mark.skip(
                    reason="Smoke tests require GATEWAY_URL env var pointing to a deployed gateway."
                )
            )


# ── Shared fixtures ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app_env() -> str:
    """The current deployment environment tier."""
    return APP_ENV


@pytest.fixture(scope="session")
def gateway_url() -> str:
    """
    Base URL of a live gateway for smoke tests.
    Set via GATEWAY_URL env var; tests are skipped automatically when absent.
    """
    if not GATEWAY_URL:
        pytest.skip("GATEWAY_URL not set — smoke tests skipped.")
    return GATEWAY_URL.rstrip("/")


@pytest.fixture(scope="session")
def localstack_url() -> str:
    """LocalStack endpoint for AWS service mocks in integration tests."""
    if not LOCALSTACK_URL:
        pytest.skip("LLMOPS_LOCALSTACK_URL not set — localstack tests skipped.")
    return LOCALSTACK_URL


@pytest.fixture(scope="session")
def qdrant_available() -> bool:
    """
    True when a Qdrant instance is reachable on localhost:6333.
    Integration tests that use Qdrant should request this fixture.
    """
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    available = _port_open(host, port)
    if not available:
        pytest.skip(
            f"Qdrant not reachable at {host}:{port}. "
            "Run: docker compose -f docker-compose.test.yml up -d qdrant"
        )
    return True


@pytest.fixture(scope="session")
def redis_available() -> bool:
    """
    True when a Redis instance is reachable on localhost:6379.
    Tests that use the semantic cache should request this fixture.
    """
    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    available = _port_open(host, port)
    if not available:
        pytest.skip(
            f"Redis not reachable at {host}:{port}. "
            "Run: docker compose -f docker-compose.test.yml up -d redis"
        )
    return True


@pytest.fixture(scope="session")
def is_production() -> bool:
    """True when running against the production environment."""
    return APP_ENV == "production"


@pytest.fixture(scope="session")
def is_staging() -> bool:
    """True when running against the staging environment."""
    return APP_ENV == "staging"


# ── Environment guard fixtures ─────────────────────────────────────────────────

@pytest.fixture
def skip_in_production(is_production):
    """Attach to tests that must never run against the production environment."""
    if is_production:
        pytest.skip("This test is disabled in the production environment.")


@pytest.fixture
def skip_in_development():
    """Attach to tests that require a deployed environment (staging or production)."""
    if APP_ENV == "development":
        pytest.skip("This test requires a deployed environment (staging or production).")
