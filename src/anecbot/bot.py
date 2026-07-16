import logging
from pathlib import Path

import aiosqlite
import discord
from discord import app_commands
from discord.ext import commands, tasks

from anecbot.features.scheduler.service import check_publications
from anecbot.utils.config import Settings
from anecbot.utils.time import utcnow
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
        """Sync command tree globally and clear stale guild-specific commands."""
        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        await bot.tree.sync()
        logger.info(
            "Logged in as %s (guilds: %d, commands synced)", bot.user, len(bot.guilds)
        )

    @tasks.loop(minutes=1)
    async def publication_loop() -> None:
        """Check every started guild and trigger publication where due, logging each tick."""
        now = utcnow()
        logger.info("Publication batch tick at %s", now.isoformat())
        try:
            triggered = await check_publications(bot, bot.db, now)
            logger.info("Publication batch: triggered %d guild(s)", triggered)
        except Exception:
            logger.exception("Publication batch failed")

    @publication_loop.before_loop
    async def before_publication_loop() -> None:
        """Wait for the bot to be ready before the first tick."""
        await bot.wait_until_ready()

    async def setup_hook() -> None:
        """Initialize the database, load cogs, and start background tasks."""
        bot.db = await init_db(settings.db_path, Path(settings.migrations_dir))
        logger.info("Database initialized")
        await bot.load_extension("anecbot.cogs")
        logger.info("Cogs loaded")
        publication_loop.start()

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
        """Stop background tasks and close the database connection before shutting down."""
        publication_loop.cancel()
        if hasattr(bot, "db"):
            await close_db(bot.db)
        await _original_close()

    bot.close = close

    return bot
