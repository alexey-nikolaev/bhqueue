"""
Application configuration using Pydantic Settings.
Loads from environment variables and .env file.
"""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "BHQueue"
    app_env: str = "development"  # development, staging, production
    debug: bool = True
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql://localhost:5432/bhqueue"

    # JWT Authentication
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    # Admin API
    admin_api_key: Optional[str] = None  # Set this for automated admin access

    # Reddit (Devvit handles this - no API credentials needed)
    # The Devvit app pushes data to our /api/queue/reddit-update endpoint

    # Telegram API
    telegram_api_id: Optional[str] = None  # Stored as string, converted when needed
    telegram_api_hash: Optional[str] = None
    telegram_phone: Optional[str] = None
    
    @property
    def telegram_api_id_int(self) -> Optional[int]:
        """Get telegram_api_id as integer."""
        if self.telegram_api_id:
            return int(self.telegram_api_id)
        return None

    # OAuth Providers
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    apple_client_id: Optional[str] = None
    apple_team_id: Optional[str] = None
    apple_key_id: Optional[str] = None
    apple_private_key: Optional[str] = None

    # Berghain specific
    berghain_subreddit: str = "Berghain_Community"
    berghain_telegram_group: str = "berghainberlin"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
