import pytest
from pydantic import ValidationError

from anecbot.utils.config import Settings


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    """Remove any of the app's env vars so each test starts from a clean slate."""
    for name in ("DISCORD_TOKEN", "DB_PATH", "MIGRATIONS_DIR", "LOG_LEVEL", "LOG_FILE"):
        monkeypatch.delenv(name, raising=False)


def test_discord_token_is_required():
    """Settings raises when DISCORD_TOKEN is missing, since it has no default."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_defaults_applied_when_only_token_given(monkeypatch):
    """Every other field falls back to its documented default."""
    monkeypatch.setenv("DISCORD_TOKEN", "token")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.discord_token == "token"
    assert settings.db_path == "data/anecbot.db"
    assert settings.migrations_dir == "migrations"
    assert settings.log_level == "INFO"
    assert settings.log_file == "data/anecbot.log"


def test_values_loaded_from_env_vars(monkeypatch):
    """Every field can be overridden via its env var alias."""
    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setenv("DB_PATH", "custom.db")
    monkeypatch.setenv("MIGRATIONS_DIR", "custom_migrations")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FILE", "custom.log")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.db_path == "custom.db"
    assert settings.migrations_dir == "custom_migrations"
    assert settings.log_level == "DEBUG"
    assert settings.log_file == "custom.log"


def test_unknown_env_vars_are_ignored(monkeypatch):
    """Extra, unrelated env vars don't cause validation to fail."""
    monkeypatch.setenv("DISCORD_TOKEN", "token")
    monkeypatch.setenv("SOME_UNRELATED_VAR", "value")

    settings = Settings(_env_file=None)  # type: ignore[call-arg]

    assert settings.discord_token == "token"
