from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded and validated from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    discord_token: str = Field(alias="DISCORD_TOKEN")
    db_path: str = Field(default="data/anecbot.db", alias="DB_PATH")
    migrations_dir: str = Field(default="migrations", alias="MIGRATIONS_DIR")
