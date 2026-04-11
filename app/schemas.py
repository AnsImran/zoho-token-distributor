"""Pydantic response models for the token service API."""

from datetime import datetime

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Payload returned by GET /token."""

    access_token: str = Field(..., description="Zoho OAuth access token", examples=["1000.abc123def456"])
    created_at: datetime = Field(..., description="UTC timestamp when the token was issued")
    expires_at: datetime = Field(..., description="UTC timestamp when the token expires")
    token_type: str = Field("Zoho-oauthtoken", description="Token type for the Authorization header")
    is_stale: bool = Field(False, description="True if the token has expired but no fresh one is available")


class HealthResponse(BaseModel):
    """Payload returned by GET /health and readiness/liveness probes."""

    status: str = Field(..., description="'ok' or 'degraded'", examples=["ok"])
    token_cached: bool = Field(..., description="Whether a token is currently in the cache")
    token_is_stale: bool = Field(False, description="True if the cached token has expired")
    expires_at: datetime | None = Field(None, description="When the cached token expires")
    refresh_loop_alive: bool = Field(False, description="Whether the background refresh loop is running")  # noqa: E501
    last_refresh_success: datetime | None = Field(None, description="When the last successful refresh occurred")


class ErrorResponse(BaseModel):
    """Standard error envelope for non-2xx responses."""

    detail: str = Field(..., description="Human-readable error message")
    request_id: str | None = Field(None, description="Correlation ID for tracing")
