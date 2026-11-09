import pytest

from app.config import Settings


def test_defaults_are_used_when_nothing_is_set() -> None:
    # _env_file=None ignores the real .env so the test is deterministic
    settings = Settings(_env_file=None)

    assert settings.claude_model == "claude-haiku-5-5"
    assert settings.max_jobs_to_score == 60


def test_env_vars_override_defaults_and_are_converted(monkeypatch: pytest.MonkeyPatch) -> None:
    # monkeypatch undoes the env change after the test (no leakage between tests)
    monkeypatch.setenv("MAX_JOBS_TO_SCORE", "10")
    monkeypatch.setenv("CLAUDE_MODEL", "some-model")

    settings = Settings(_env_file=None)

    assert settings.max_jobs_to_score == 10  # string "10" became int
    assert settings.claude_model == "some-model"


def test_secrets_are_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-super-secret")

    settings = Settings(_env_file=None)

    assert "sk-super-secret" not in repr(settings)
    assert settings.anthropic_api_key.get_secret_value() == "sk-super-secret"
