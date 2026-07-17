import sys

from discord import LoginFailure
from pydantic import ValidationError

from anecbot.bot import create_bot
from anecbot.utils.config import Settings
from anecbot.utils.logging import setup_logging

try:
    # pyright doesn't know BaseSettings fills required fields from the environment.
    settings = Settings()  # pyright: ignore[reportCallIssue]
except ValidationError as exc:
    missing = ", ".join(str(error["loc"][0]) for error in exc.errors())
    sys.exit(
        f"Invalid environment configuration, missing or invalid: {missing}. "
        "Copy .env.example to .env and fill in the values."
    )

setup_logging(level=settings.log_level, log_file=settings.log_file)

bot = create_bot(settings)
try:
    bot.run(settings.discord_token)
except LoginFailure:
    sys.exit("Invalid Discord token. Check DISCORD_TOKEN in your .env file.")
