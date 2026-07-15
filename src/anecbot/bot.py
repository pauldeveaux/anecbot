import logging
from pathlib import Path

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands

from anecbot.utils.config import Settings
from anecbot.models.database import close_db, init_db

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    """Bot subclass with a database connection attribute."""

    db: aiosqlite.Connection


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Discord bot with database lifecycle hooks."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        """Sync command tree per guild and log connection status."""
        for guild in bot.guilds:
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        logger.info(
            "Logged in as %s (guilds: %d, commands synced)", bot.user, len(bot.guilds)
        )

    async def setup_hook() -> None:
        """Initialize the database and load cogs before the bot starts receiving events."""
        bot.db = await init_db(settings.db_path, Path(settings.migrations_dir))
        logger.info("Database initialized")
        await bot.load_extension("anecbot.cogs")
        logger.info("Cogs loaded")

    bot.setup_hook = setup_hook

    @bot.event
    async def on_interaction(interaction: discord.Interaction):
        """Log all incoming interactions."""
        logger.debug(
            "Interaction: type=%s, command=%s, data=%s",
            interaction.type,
            interaction.command.name if interaction.command else "none",
            interaction.data,
        )

    @bot.tree.error
    async def on_app_command_error(
        interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        """Handle slash command errors with ephemeral French messages."""
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "❌ Tu n'as pas la permission d'utiliser cette commande.",
                ephemeral=True,
            )
        else:
            logger.error(
                "Unhandled command error in '%s' (data=%s): %s",
                interaction.command.name if interaction.command else "unknown",
                interaction.data,
                error,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Une erreur est survenue.",
                    ephemeral=True,
                )

    _original_close = bot.close

    async def close() -> None:
        """Close the database connection before shutting down the bot."""
        if hasattr(bot, "db"):
            await close_db(bot.db)
        await _original_close()

    bot.close = close

    return bot
