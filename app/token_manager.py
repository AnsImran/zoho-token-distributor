"""Async token cache with proactive background refresh.

Design rules
-------------
- ``_TOKEN_CACHE`` is the **only** token slot in memory.
- On refresh the entire dict is replaced (old one is GC'd immediately).
- A background ``asyncio.Task`` sleeps until 2 minutes before expiry,
  then fetches a fresh token.  On failure it backs off 15 s and retries.
- Uses ``httpx.AsyncClient`` (async-native) instead of blocking ``requests``.
- Intended to run behind **--workers 1** so there is exactly one cache.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOKEN_LIFETIME_SECONDS: int    = 3600   # Zoho access tokens last one hour.
PROACTIVE_REFRESH_SECONDS: int = 120    # Refresh 2 minutes before expiry.
RETRY_BACKOFF_SECONDS: int     = 15     # Wait after a failed refresh attempt.

ZOHO_ACCOUNTS_TOKEN_URL: str = os.getenv(
    "ZOHO_ACCOUNTS_TOKEN_URL",
    "https://accounts.zoho.com/oauth/v2/token",
)

# ---------------------------------------------------------------------------
# Single-slot cache (module-level state)
# ---------------------------------------------------------------------------

_TOKEN_CACHE: Dict[str, Any] = {"token": None, "created_at": None, "expires_at": None}
_refresh_task: Optional[asyncio.Task] = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _env_required(key: str) -> str:
    """Return env var value or raise with a clear message."""
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {key!r} is missing or empty.")
    return value


async def _fetch_fresh_token() -> Dict[str, Any]:
    """POST to Zoho OAuth and return a new cache dict.

    The returned dict **replaces** ``_TOKEN_CACHE`` in one assignment so the
    old dict can be garbage-collected immediately.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            ZOHO_ACCOUNTS_TOKEN_URL,
            data={
                "refresh_token": _env_required("ZOHO_REFRESH_TOKEN"),
                "client_id":     _env_required("ZOHO_CLIENT_ID"),
                "client_secret": _env_required("ZOHO_CLIENT_SECRET"),
                "grant_type":    "refresh_token",
            },
            timeout=30.0,
        )
        response.raise_for_status()

    payload = response.json()
    token = (payload.get("access_token") or "").strip()
    if not token:
        raise RuntimeError("Zoho token response contained an empty access_token.")

    now_utc = datetime.now(timezone.utc)
    return {
        "token":      token,
        "created_at": now_utc,
        "expires_at": now_utc + timedelta(seconds=TOKEN_LIFETIME_SECONDS),
    }


async def _refresh_loop() -> None:
    """Sleep until near-expiry, then replace the cached token.  Repeat forever."""
    global _TOKEN_CACHE

    while True:
        try:
            expires_at = _TOKEN_CACHE.get("expires_at")
            if expires_at is not None:
                remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
                sleep_for = max(remaining - PROACTIVE_REFRESH_SECONDS, 0)
                if sleep_for > 0:
                    logger.info("Next proactive refresh in %.0f s.", sleep_for)
                    await asyncio.sleep(sleep_for)

            logger.info("Proactively refreshing Zoho token...")
            _TOKEN_CACHE = await _fetch_fresh_token()
            logger.info(
                "Token refreshed — expires at %s.",
                _TOKEN_CACHE["expires_at"].isoformat(),
            )
        except asyncio.CancelledError:
            logger.info("Refresh loop cancelled — shutting down.")
            raise
        except Exception:
            logger.exception("Token refresh failed — retrying in %d s.", RETRY_BACKOFF_SECONDS)
            await asyncio.sleep(RETRY_BACKOFF_SECONDS)


# ---------------------------------------------------------------------------
# Public API (called by FastAPI lifespan / route handlers)
# ---------------------------------------------------------------------------

async def start_background_refresh() -> None:
    """Eagerly fetch the first token, then launch the background refresh loop."""
    global _TOKEN_CACHE, _refresh_task

    logger.info("Fetching initial Zoho token...")
    _TOKEN_CACHE = await _fetch_fresh_token()
    logger.info("Initial token cached — expires at %s.", _TOKEN_CACHE["expires_at"].isoformat())

    _refresh_task = asyncio.create_task(_refresh_loop())


async def stop_background_refresh() -> None:
    """Cancel the background refresh task cleanly."""
    global _refresh_task

    if _refresh_task is not None:
        _refresh_task.cancel()
        try:
            await _refresh_task
        except asyncio.CancelledError:
            pass
        _refresh_task = None
        logger.info("Background refresh task stopped.")


def get_cached_token() -> Dict[str, Any]:
    """Return a shallow copy of the current token cache.

    Raises ``RuntimeError`` if no token has been fetched yet.
    """
    if _TOKEN_CACHE["token"] is None:
        raise RuntimeError("Token not yet available — service is still starting.")
    return dict(_TOKEN_CACHE)
