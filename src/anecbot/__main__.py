import sys

from pydantic import ValidationError

from anecbot.bot import create_bot
from anecbot.config import Settings
from anecbot.logging import setup_logging

setup_logging()

try:
    # pyright doesn't know BaseSettings fills required fields from the environment.
    settings = Settings()  # pyright: ignore[reportCallIssue]
except ValidationError as exc:
    missing = ", ".join(str(error["loc"][0]) for error in exc.errors())
    sys.exit(
        f"Invalid environment configuration, missing or invalid: {missing}. "
        "Copy .env.example to .env and fill in the values."
    )

bot = create_bot(settings)
bot.run(settings.discord_token)
