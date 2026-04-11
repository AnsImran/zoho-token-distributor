"""Async token cache with proactive background refresh.

Design rules
-------------
- ``_TOKEN_CACHE`` is the **only** token slot in memory.
- On refresh the entire dict is replaced (old one is GC'd immediately).
- A background ``asyncio.Task`` sleeps until 2 minutes before expiry,
  then fetches a fresh token.  On failure it backs off with exponential
  backoff + jitter and retries.
- Uses ``httpx.AsyncClient`` (async-native) instead of blocking ``requests``.
- Intended to run behind **--workers 1** so there is exactly one cache.
"""

import asyncio
import contextlib
import logging
import random
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Single-slot cache (module-level state)
# ---------------------------------------------------------------------------

_TOKEN_CACHE: dict[str, Any] = {"token": None, "created_at": None, "expires_at": None}
_refresh_task: asyncio.Task | None = None
_last_refresh_success: datetime | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _fetch_fresh_token() -> dict[str, Any]:
    """POST to Zoho OAuth and return a new cache dict.

    The returned dict **replaces** ``_TOKEN_CACHE`` in one assignment so the
    old dict can be garbage-collected immediately.
    """
    settings = get_settings()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.zoho_accounts_token_url,
            data={
                "refresh_token": settings.zoho_refresh_token,
                "client_id": settings.zoho_client_id,
                "client_secret": settings.zoho_client_secret,
                "grant_type": "refresh_token",
            },
            timeout=30.0,
        )
        response.raise_for_status()

    payload = response.json()
    token = (payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Zoho token response contained an empty access_token.")

    now_utc = datetime.now(UTC)
    return {
        "token": token,
        "created_at": now_utc,
        "expires_at": now_utc + timedelta(seconds=settings.token_lifetime_seconds),
    }


async def _refresh_loop() -> None:
    """Sleep until near-expiry, then replace the cached token.  Repeat forever."""
    global _TOKEN_CACHE, _last_refresh_success
    settings = get_settings()
    consecutive_failures = 0

    while True:
        try:
            expires_at = _TOKEN_CACHE.get("expires_at")
            if expires_at is not None:
                remaining = (expires_at - datetime.now(UTC)).total_seconds()
                sleep_for = max(remaining - settings.proactive_refresh_seconds, 0)
                if sleep_for > 0:
                    logger.info("Next proactive refresh in %.0f s.", sleep_for)
                    await asyncio.sleep(sleep_for)

            logger.info("Proactively refreshing Zoho token...")
            _TOKEN_CACHE = await _fetch_fresh_token()
            _last_refresh_success = datetime.now(UTC)
            consecutive_failures = 0
            logger.info(
                "Token refreshed — expires at %s.",
                _TOKEN_CACHE["expires_at"].isoformat(),
            )
        except asyncio.CancelledError:
            logger.info("Refresh loop cancelled — shutting down.")
            raise
        except Exception:
            consecutive_failures += 1
            delay = min(
                settings.retry_backoff_base_seconds * (2 ** (consecutive_failures - 1)),
                settings.retry_backoff_max_seconds,
            )
            delay *= 0.5 + random.random() * 0.5  # jitter
            logger.exception(
                "Token refresh failed (attempt %d) — retrying in %.1f s.",
                consecutive_failures,
                delay,
            )
            await asyncio.sleep(delay)


# ---------------------------------------------------------------------------
# Public API (called by FastAPI lifespan / route handlers)
# ---------------------------------------------------------------------------


async def start_background_refresh() -> None:
    """Eagerly fetch the first token, then launch the background refresh loop."""
    global _TOKEN_CACHE, _refresh_task, _last_refresh_success

    logger.info("Fetching initial Zoho token...")
    try:
        _TOKEN_CACHE = await _fetch_fresh_token()
        _last_refresh_success = datetime.now(UTC)
        logger.info("Initial token cached — expires at %s.", _TOKEN_CACHE["expires_at"].isoformat())
    except Exception:
        logger.exception("Initial token fetch failed — will retry in background.")

    _refresh_task = asyncio.create_task(_refresh_loop())


async def stop_background_refresh() -> None:
    """Cancel the background refresh task cleanly."""
    global _refresh_task

    if _refresh_task is not None:
        _refresh_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await _refresh_task
        _refresh_task = None
        logger.info("Background refresh task stopped.")


def get_cached_token() -> dict[str, Any]:
    """Return a shallow copy of the current token cache.

    Raises ``RuntimeError`` if no token has been fetched yet.
    Includes ``is_stale`` flag when the token has expired.
    """
    if _TOKEN_CACHE["token"] is None:
        raise RuntimeError("Token not yet available — service is still starting.")
    result = dict(_TOKEN_CACHE)
    result["is_stale"] = _TOKEN_CACHE["expires_at"] < datetime.now(UTC)
    return result


def get_refresh_status() -> dict[str, Any]:
    """Return status of the background refresh loop."""
    return {
        "loop_alive": _refresh_task is not None and not _refresh_task.done(),
        "last_success": _last_refresh_success,
    }
