"""Shared fixtures for all test modules."""

import pytest


@pytest.fixture(autouse=True)
def _set_dummy_env_vars(monkeypatch):
    """Ensure Zoho env vars are always set so Settings() can be instantiated in CI."""
    monkeypatch.setenv("ZOHO_REFRESH_TOKEN", "test-refresh-token")
    monkeypatch.setenv("ZOHO_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("ZOHO_CLIENT_SECRET", "test-client-secret")


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Clear the lru_cache on get_settings before/after every test."""
    from app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
