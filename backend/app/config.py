"""Application settings loaded from environment variables and the .env file."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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
    # Minimum gap between "collect now" runs (Remotive allows ~4 requests/day)
    collect_cooldown_minutes: int = 120
    timezone: str = "America/Maceio"

    # The only origin allowed by CORS (the local React dev server)
    frontend_origin: str = "http://localhost:5173"

    # NoDecode: don't expect JSON in the env var; split_comma_separated parses it
    gupy_search_terms: Annotated[list[str], NoDecode] = [
        "desenvolvedor",
        "developer",
        "programador",
        "engenheiro de software",
        "full stack",
        "backend",
    ]

    # Community job repositories on GitHub ("owner/name"), one source each
    github_job_repos: Annotated[list[str], NoDecode] = [
        "backend-br/vagas",
        "frontendbr/vagas",
        "soujava/vagas-java",
        "CocoaHeadsBrasil/vagas",
        "react-brasil/vagas",
        "phpdevbr/vagas",
        "androiddevbr/vagas",
        "vuejs-br/vagas",
        "qa-brasil/vagas",
    ]

    @field_validator("gupy_search_terms", "github_job_repos", mode="before")
    @classmethod
    def split_comma_separated(cls, value: Any) -> Any:
        """Accept "a, b,c" in .env and turn it into ["a", "b", "c"]."""
        if isinstance(value, str):
            return [term.strip() for term in value.split(",") if term.strip()]
        return value


# Decorator: wraps the function so the first result is cached and reused.
# The .env is read only once, like a singleton registered in C# DI.
@lru_cache
def get_settings() -> Settings:
    return Settings()
