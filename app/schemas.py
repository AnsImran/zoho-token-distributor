"""Pydantic response models for the token service API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class TokenResponse(BaseModel):
    """Payload returned by GET /token."""
    access_token: str
    created_at:   datetime
    expires_at:   datetime
    token_type:   str = "Zoho-oauthtoken"


class HealthResponse(BaseModel):
    """Payload returned by GET /health."""
    status:       str
    token_cached: bool
    expires_at:   Optional[datetime] = None
