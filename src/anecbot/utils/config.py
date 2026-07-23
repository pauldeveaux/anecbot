from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded and validated from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    discord_token: str = Field(alias="DISCORD_TOKEN")
    database_url: str = Field(alias="DATABASE_URL")
    migrations_dir: str = Field(default="migrations", alias="MIGRATIONS_DIR")
    release_notes_path: str = Field(
        default="RELEASE_NOTES.md", alias="RELEASE_NOTES_PATH"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_file: str = Field(default="data/anecbot.log", alias="LOG_FILE")
