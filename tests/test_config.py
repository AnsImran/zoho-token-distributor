"""Tests for the configuration module."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings, get_settings



def test_settings_requires_zoho_refresh_token(monkeypatch):
    """Missing ZOHO_REFRESH_TOKEN should raise ValidationError."""
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "cs")
    monkeypatch.delenv("ZOHO_REFRESH_TOKEN", raising=False)
    with pytest.raises(ValidationError, match="zoho_refresh_token"):
        Settings(_env_file=None)


def test_settings_requires_zoho_client_id(monkeypatch):
    """Missing ZOHO_CLIENT_ID should raise ValidationError."""
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "cs")
    monkeypatch.delenv("ZOHO_CLIENT_ID", raising=False)
    with pytest.raises(ValidationError, match="zoho_client_id"):
        Settings(_env_file=None)


def test_settings_requires_zoho_client_secret(monkeypatch):
    """Missing ZOHO_CLIENT_SECRET should raise ValidationError."""
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.delenv("ZOHO_CLIENT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="zoho_client_secret"):
        Settings(_env_file=None)


def test_settings_defaults(monkeypatch):
    """Default values should be sensible."""
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "cs")
    s = Settings(_env_file=None)

    assert s.zoho_accounts_token_url == "https://accounts.zoho.com/oauth/v2/token"
    assert s.token_lifetime_seconds == 3600
    assert s.proactive_refresh_seconds == 120
    assert s.retry_backoff_base_seconds == 2.0
    assert s.retry_backoff_max_seconds == 120.0
    assert s.log_level == "INFO"
    assert s.log_format == "json"


def test_settings_overrides(monkeypatch):
    """Env vars should override defaults."""
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "cid")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "cs")
    monkeypatch.setenv("TOKEN_LIFETIME_SECONDS", "7200")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = Settings(_env_file=None)

    assert s.token_lifetime_seconds == 7200
    assert s.log_level == "DEBUG"
