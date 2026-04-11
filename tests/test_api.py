"""Tests for the FastAPI endpoints (GET /token, GET /health).

Uses FastAPI's TestClient to exercise the HTTP layer — status codes,
response shapes, and Pydantic serialisation — without hitting Zoho.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import token_manager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fake_cache(seconds_remaining: float = 3000.0) -> dict[str, Any]:
    now = datetime.now(UTC)
    return {
        "token": "fake-token-abc",
        "created_at": now - timedelta(seconds=3600 - seconds_remaining),
        "expires_at": now + timedelta(seconds=seconds_remaining),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset module-level cache before/after every test."""
    token_manager._TOKEN_CACHE = {"token": None, "created_at": None, "expires_at": None}
    token_manager._refresh_task = None
    yield
    token_manager._TOKEN_CACHE = {"token": None, "created_at": None, "expires_at": None}
    token_manager._refresh_task = None


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on get_settings so tests are isolated."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def client():
    """TestClient that skips the real lifespan (no Zoho calls)."""
    # Override lifespan to be a no-op so we control cache state in tests.
    from contextlib import asynccontextmanager

    from app.main import app

    @asynccontextmanager
    async def _noop_lifespan(app):
        yield

    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /token
# ---------------------------------------------------------------------------


class TestGetToken:
    def test_returns_token_when_cached(self, client):
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token")

        assert resp.status_code == 200
        body = resp.json()
        assert body["access_token"] == "fake-token-abc"
        assert body["token_type"] == "Zoho-oauthtoken"
        assert "created_at" in body
        assert "expires_at" in body

    def test_returns_503_when_no_token(self, client):
        resp = client.get("/token")

        assert resp.status_code == 503
        assert "not yet available" in resp.json()["detail"]

    def test_response_matches_schema(self, client):
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token")
        body = resp.json()

        assert set(body.keys()) == {"access_token", "created_at", "expires_at", "token_type", "is_stale"}

    def test_timestamps_are_iso_format(self, client):
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token")
        body = resp.json()

        # Should parse without error.
        datetime.fromisoformat(body["created_at"])
        datetime.fromisoformat(body["expires_at"])

    def test_expires_at_is_after_created_at(self, client):
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token")
        body = resp.json()

        created = datetime.fromisoformat(body["created_at"])
        expires = datetime.fromisoformat(body["expires_at"])
        assert expires > created


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealth:
    def test_returns_ok_with_cached_token(self, client):
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["token_cached"] is True
        assert body["expires_at"] is not None

    def test_returns_degraded_without_cached_token(self, client):
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["token_cached"] is False
        assert body["expires_at"] is None

    def test_health_never_returns_error_status(self, client):
        """Health should always be 200, even with no token."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_response_matches_schema(self, client):
        resp = client.get("/health")
        body = resp.json()

        expected_keys = {
            "status",
            "token_cached",
            "token_is_stale",
            "expires_at",
            "refresh_loop_alive",
            "last_refresh_success",
        }
        assert set(body.keys()) == expected_keys

    def test_healthz_always_200(self, client):
        """Liveness probe should always return 200."""
        resp = client.get("/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_readyz_reports_status(self, client):
        """Readiness probe should report degraded when no token."""
        resp = client.get("/readyz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "degraded"
        assert resp.json()["token_cached"] is False


# ---------------------------------------------------------------------------
# New feature tests (Phase 8)
# ---------------------------------------------------------------------------


class TestAPIVersioning:
    def test_v1_token_endpoint(self, client):
        """GET /v1/token should work identically to /token."""
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/v1/token")
        assert resp.status_code == 200
        assert resp.json()["access_token"] == "fake-token-abc"

    def test_v1_healthz_endpoint(self, client):
        """GET /v1/healthz should return liveness probe."""
        resp = client.get("/v1/healthz")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_v1_readyz_endpoint(self, client):
        """GET /v1/readyz should return readiness probe."""
        resp = client.get("/v1/readyz")
        assert resp.status_code == 200


class TestResponseHeaders:
    def test_request_id_header_returned(self, client):
        """Responses should include X-Request-ID header."""
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token")
        assert "X-Request-ID" in resp.headers

    def test_request_id_echoed_when_provided(self, client):
        """When caller provides X-Request-ID, it should be echoed back."""
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token", headers={"X-Request-ID": "test-123"})
        assert resp.headers["X-Request-ID"] == "test-123"

    def test_cache_control_header_on_token(self, client):
        """GET /token should include Cache-Control header."""
        token_manager._TOKEN_CACHE = _fake_cache()
        resp = client.get("/token")
        assert "Cache-Control" in resp.headers
        assert resp.headers["Cache-Control"].startswith("private, max-age=")


class TestStaleTokenHandling:
    def test_stale_token_returns_200_with_flag(self, client):
        """Expired token should still return 200, with is_stale=True."""
        token_manager._TOKEN_CACHE = _fake_cache(seconds_remaining=-60)
        resp = client.get("/token")
        assert resp.status_code == 200
        assert resp.json()["is_stale"] is True

    def test_fresh_token_has_is_stale_false(self, client):
        """Fresh token should have is_stale=False."""
        token_manager._TOKEN_CACHE = _fake_cache(seconds_remaining=3000)
        resp = client.get("/token")
        assert resp.status_code == 200
        assert resp.json()["is_stale"] is False

    def test_readyz_reports_degraded_when_stale(self, client):
        """Readiness probe should report degraded for stale token."""
        token_manager._TOKEN_CACHE = _fake_cache(seconds_remaining=-60)
        resp = client.get("/readyz")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["token_is_stale"] is True
