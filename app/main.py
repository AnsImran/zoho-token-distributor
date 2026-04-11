"""FastAPI application for the Zoho Token Service.

Exposes versioned endpoints under ``/v1/`` with backward-compatible aliases
at the root (``/token``, ``/health``).
"""

import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from .config import get_settings
from .logging_config import setup_logging
from .middleware import RequestLoggingMiddleware
from .schemas import HealthResponse, TokenResponse
from .token_manager import get_cached_token, get_refresh_status, start_background_refresh, stop_background_refresh

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: validate config, set up logging, fetch token, launch loop.  Shutdown: clean cancel."""
    settings = get_settings()  # fail fast if env vars missing
    setup_logging(level=settings.log_level, fmt=settings.log_format)
    await start_background_refresh()
    yield
    await stop_background_refresh()


# ---------------------------------------------------------------------------
# App + middleware
# ---------------------------------------------------------------------------

app = FastAPI(title="Zoho Token Service", lifespan=lifespan)
app.add_middleware(RequestLoggingMiddleware)


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch unhandled exceptions — log full traceback, return generic error."""
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled exception", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "request_id": request_id},
    )


# ---------------------------------------------------------------------------
# Versioned router
# ---------------------------------------------------------------------------

v1 = APIRouter(prefix="/v1", tags=["v1"])


@v1.get("/token", response_model=TokenResponse)
async def get_token(response: Response):
    """Return the current cached Zoho access token."""
    try:
        cache = get_cached_token()
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail="Token not yet available.") from err

    remaining = max(int((cache["expires_at"] - datetime.now(UTC)).total_seconds()), 0)
    response.headers["Cache-Control"] = f"private, max-age={min(remaining, 60)}"

    return TokenResponse(
        access_token=cache["token"],
        created_at=cache["created_at"],
        expires_at=cache["expires_at"],
        is_stale=cache.get("is_stale", False),
    )


@v1.get("/healthz", response_model=HealthResponse)
async def liveness():
    """Liveness probe — is the process alive?"""
    return HealthResponse(status="ok", token_cached=False)


@v1.get("/readyz", response_model=HealthResponse)
async def readiness():
    """Readiness probe — can the service serve valid tokens?"""
    refresh = get_refresh_status()
    try:
        cache = get_cached_token()
        is_stale = cache.get("is_stale", False)
        return HealthResponse(
            status="degraded" if is_stale else "ok",
            token_cached=True,
            token_is_stale=is_stale,
            expires_at=cache["expires_at"],
            refresh_loop_alive=refresh["loop_alive"],
            last_refresh_success=refresh["last_success"],
        )
    except RuntimeError:
        return HealthResponse(
            status="degraded",
            token_cached=False,
            refresh_loop_alive=refresh["loop_alive"],
        )


app.include_router(v1)


# ---------------------------------------------------------------------------
# Backward-compatible root aliases (not shown in OpenAPI docs)
# ---------------------------------------------------------------------------


@app.get("/token", response_model=TokenResponse, include_in_schema=False)
async def get_token_compat(response: Response):
    """Backward-compatible alias for /v1/token."""
    return await get_token(response)


@app.get("/healthz", response_model=HealthResponse, include_in_schema=False)
async def liveness_compat():
    """Backward-compatible alias for /v1/healthz."""
    return await liveness()


@app.get("/readyz", response_model=HealthResponse, include_in_schema=False)
@app.get("/health", response_model=HealthResponse, include_in_schema=False)
async def readiness_compat():
    """Backward-compatible alias for /v1/readyz."""
    return await readiness()
