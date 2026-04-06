"""Tests for the FastAPI endpoints (GET /token, GET /health).

Uses FastAPI's TestClient to exercise the HTTP layer — status codes,
response shapes, and Pydantic serialisation — without hitting Zoho.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import token_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_cache(seconds_remaining: float = 3000.0) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    return {
        "token":      "fake-token-abc",
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


@pytest.fixture()
def client():
    """TestClient that skips the real lifespan (no Zoho calls)."""
    from app.main import app

    # Override lifespan to be a no-op so we control cache state in tests.
    from contextlib import asynccontextmanager

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

        assert set(body.keys()) == {"access_token", "created_at", "expires_at", "token_type"}

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

    def test_returns_ok_without_cached_token(self, client):
        resp = client.get("/health")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["token_cached"] is False
        assert body["expires_at"] is None

    def test_health_never_returns_error_status(self, client):
        """Health should always be 200, even with no token."""
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_response_matches_schema(self, client):
        resp = client.get("/health")
        body = resp.json()

        assert set(body.keys()) == {"status", "token_cached", "expires_at"}
