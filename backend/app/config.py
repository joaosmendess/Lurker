"""Application settings loaded from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ folder. Anchoring the .env path here makes it work no matter
# which directory the process was started from.
BACKEND_DIR: Path = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Every setting of the app. Field names map to env vars case-insensitively
    (claude_model <- CLAUDE_MODEL)."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",  # unknown keys in .env don't break startup
    )

    # SecretStr hides the value in repr/logs: printing it shows '**********'
    anthropic_api_key: SecretStr = SecretStr("")
    claude_model: str = "claude-haiku-5-5"

    database_url: str = "sqlite:///lurker.db"

    max_jobs_to_score: int = 60
    min_score_to_email: int = 65

    gmail_user: str = ""
    gmail_app_password: SecretStr = SecretStr("")
    email_to: str = ""

    collect_cron: str = "0 7 * * 1-5"
    timezone: str = "America/Maceio"


# Decorator: wraps the function so the first result is cached and reused.
# The .env is read only once, like a singleton registered in C# DI.
@lru_cache
def get_settings() -> Settings:
    return Settings()
