"""Centralised, validated configuration via pydantic-settings.

All required environment variables are validated at startup.
Missing or invalid values cause an immediate, clear error.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Zoho OAuth (required)
    zoho_refresh_token: str
    zoho_client_id: str
    zoho_client_secret: str
    zoho_accounts_token_url: str = "https://accounts.zoho.com/oauth/v2/token"

    # Token timing (seconds)
    token_lifetime_seconds: int = 3600
    proactive_refresh_seconds: int = 120
    retry_backoff_base_seconds: float = 2.0
    retry_backoff_max_seconds: float = 120.0

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "text"


@lru_cache
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()
