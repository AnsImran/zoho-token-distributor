"""Async unit tests for token_manager (the core of the token service)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from app import token_manager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_cache(seconds_remaining: float = 3000.0) -> Dict[str, Any]:
    """Return a realistic cache dict that expires in *seconds_remaining*."""
    now = datetime.now(timezone.utc)
    return {
        "token":      "fake-token-abc",
        "created_at": now - timedelta(seconds=3600 - seconds_remaining),
        "expires_at": now + timedelta(seconds=seconds_remaining),
    }


def _make_mock_fetch(token: str = "new-token-xyz") -> AsyncMock:
    """Create an AsyncMock that returns a fresh cache dict."""
    now = datetime.now(timezone.utc)
    return AsyncMock(return_value={
        "token":      token,
        "created_at": now,
        "expires_at": now + timedelta(seconds=3600),
    })


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_module_state():
    """Reset module-level cache and task before/after every test."""
    token_manager._TOKEN_CACHE = {"token": None, "created_at": None, "expires_at": None}
    token_manager._refresh_task = None
    yield
    token_manager._TOKEN_CACHE = {"token": None, "created_at": None, "expires_at": None}
    token_manager._refresh_task = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_fresh_token_populates_cache(monkeypatch):
    """After _fetch_fresh_token, all three cache fields should be non-None."""
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "cs")

    fake_response = AsyncMock()
    fake_response.status_code = 200
    fake_response.raise_for_status = lambda: None
    fake_response.json = lambda: {"access_token": "tok-123"}  # httpx .json() is sync, not async.

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=fake_response)

    with patch("app.token_manager.httpx.AsyncClient", return_value=mock_client):
        result = await token_manager._fetch_fresh_token()

    assert result["token"] == "tok-123"
    assert result["created_at"] is not None
    assert result["expires_at"] is not None
    assert result["expires_at"] > result["created_at"]


def test_get_cached_token_raises_when_empty():
    """get_cached_token should raise RuntimeError when no token is cached."""
    with pytest.raises(RuntimeError, match="not yet available"):
        token_manager.get_cached_token()


def test_get_cached_token_returns_copy():
    """Mutating the returned dict must NOT change _TOKEN_CACHE."""
    token_manager._TOKEN_CACHE = _fake_cache()
    copy = token_manager.get_cached_token()
    copy["token"] = "mutated"
    assert token_manager._TOKEN_CACHE["token"] == "fake-token-abc"


@pytest.mark.asyncio
async def test_proactive_refresh_replaces_cache():
    """After a proactive refresh, cache should contain the new token."""
    token_manager._TOKEN_CACHE = _fake_cache(seconds_remaining=60)  # < 120 s threshold

    mock_fetch = _make_mock_fetch("refreshed-token")
    with patch.object(token_manager, "_fetch_fresh_token", mock_fetch):
        loop_task = asyncio.create_task(token_manager._refresh_loop())
        await asyncio.sleep(0.1)  # Let the loop run once.
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

    assert token_manager._TOKEN_CACHE["token"] == "refreshed-token"
    mock_fetch.assert_awaited_once()


@pytest.mark.asyncio
async def test_refresh_loop_retries_after_failure():
    """On fetch failure, the loop should back off and retry."""
    token_manager._TOKEN_CACHE = _fake_cache(seconds_remaining=60)

    call_count = 0
    async def _failing_then_succeeding():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated Zoho error")
        now = datetime.now(timezone.utc)
        return {"token": "retry-ok", "created_at": now, "expires_at": now + timedelta(seconds=3600)}

    with patch.object(token_manager, "_fetch_fresh_token", side_effect=_failing_then_succeeding):
        with patch.object(token_manager, "RETRY_BACKOFF_SECONDS", 0.05):  # Speed up test.
            loop_task = asyncio.create_task(token_manager._refresh_loop())
            await asyncio.sleep(0.3)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass

    assert call_count >= 2
    assert token_manager._TOKEN_CACHE["token"] == "retry-ok"


@pytest.mark.asyncio
async def test_background_task_created_on_startup():
    """start_background_refresh should populate cache and create a live task."""
    mock_fetch = _make_mock_fetch("startup-token")
    with patch.object(token_manager, "_fetch_fresh_token", mock_fetch):
        await token_manager.start_background_refresh()

    assert token_manager._TOKEN_CACHE["token"] == "startup-token"
    assert token_manager._refresh_task is not None
    assert not token_manager._refresh_task.done()

    # Clean up the background task.
    await token_manager.stop_background_refresh()


@pytest.mark.asyncio
async def test_stop_cancels_task_cleanly():
    """stop_background_refresh should cancel without raising."""
    mock_fetch = _make_mock_fetch()
    with patch.object(token_manager, "_fetch_fresh_token", mock_fetch):
        await token_manager.start_background_refresh()
        await token_manager.stop_background_refresh()

    assert token_manager._refresh_task is None


@pytest.mark.asyncio
async def test_120s_grace_triggers_immediate_refresh():
    """With < 120 s remaining, the loop should refresh immediately (no long sleep)."""
    token_manager._TOKEN_CACHE = _fake_cache(seconds_remaining=90)  # 90 s < 120 s threshold.

    mock_fetch = _make_mock_fetch("immediate-token")
    with patch.object(token_manager, "_fetch_fresh_token", mock_fetch):
        loop_task = asyncio.create_task(token_manager._refresh_loop())
        await asyncio.sleep(0.1)
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass

    assert token_manager._TOKEN_CACHE["token"] == "immediate-token"
    mock_fetch.assert_awaited_once()
