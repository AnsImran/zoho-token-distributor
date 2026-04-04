"""FastAPI application for the Zoho Token Service.

Exposes two endpoints:
- GET /token  — returns the current cached Zoho access token
- GET /health — lightweight health check for Docker / load balancer probes
"""

import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from .schemas import HealthResponse, TokenResponse
from .token_manager import get_cached_token, start_background_refresh, stop_background_refresh

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: eager token fetch + background loop.  Shutdown: clean cancel."""
    await start_background_refresh()
    yield
    await stop_background_refresh()


app = FastAPI(title="Zoho Token Service", lifespan=lifespan)


@app.get("/token", response_model=TokenResponse)
async def get_token():
    """Return the current cached Zoho access token."""
    try:
        cache = get_cached_token()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return TokenResponse(
        access_token=cache["token"],
        created_at=cache["created_at"],
        expires_at=cache["expires_at"],
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Lightweight health probe — reports whether a token is cached."""
    try:
        cache = get_cached_token()
        return HealthResponse(status="ok", token_cached=True, expires_at=cache["expires_at"])
    except RuntimeError:
        return HealthResponse(status="ok", token_cached=False)
