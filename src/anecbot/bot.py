import logging

import discord
from discord.ext import commands

from anecbot.models.database import close_db, init_db

logger = logging.getLogger(__name__)


def create_bot() -> commands.Bot:
    """Create and configure the Discord bot with database lifecycle hooks."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        """Log bot connection status and guild count."""
        logger.info("Logged in as %s (guilds: %d)", bot.user, len(bot.guilds))

    async def setup_hook() -> None:
        """Initialize the database connection before the bot starts receiving events."""
        bot.db = await init_db()
        logger.info("Database initialized")

    bot.setup_hook = setup_hook

    _original_close = bot.close

    async def close() -> None:
        """Close the database connection before shutting down the bot."""
        await close_db(bot.db)
        await _original_close()

    bot.close = close

    return bot
