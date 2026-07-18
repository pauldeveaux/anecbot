import asyncio
import logging
from pathlib import Path

import discord
import psycopg
from discord import app_commands
from discord.ext import commands, tasks

from anecbot.features.lifecycle.service import purge_guild
from anecbot.features.publisher.service import restore_active_views
from anecbot.features.scheduler.service import (
    check_leaderboard_resets,
    check_publications,
    check_reveals,
)
from anecbot.utils.config import Settings
from anecbot.utils.time import utcnow
from anecbot.models.database import close_db, init_db

logger = logging.getLogger(__name__)


class Bot(commands.Bot):
    """Bot subclass with a database connection attribute."""

    db: psycopg.AsyncConnection


def create_bot(settings: Settings) -> Bot:
    """Create and configure the Discord bot with database lifecycle hooks."""
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = Bot(command_prefix="!", intents=intents)
    views_restored = False

    @bot.event
    async def on_ready():
        """Sync command tree, clear stale guild-specific commands, restore MCQ views once."""
        for guild in bot.guilds:
            bot.tree.clear_commands(guild=guild)
            await bot.tree.sync(guild=guild)
        await bot.tree.sync()
        logger.info(
            "Logged in as %s (guilds: %d, commands synced)", bot.user, len(bot.guilds)
        )

        nonlocal views_restored
        if not views_restored:
            await restore_active_views(bot, bot.db)
            views_restored = True

    @bot.event
    async def on_guild_remove(guild: discord.Guild):
        """Purge the guild's data once the bot is no longer a member."""
        await purge_guild(bot.db, guild.id)

    @tasks.loop(minutes=1)
    async def batch_loop() -> None:
        """Run one batch tick: publications, then reveals, then leaderboard resets."""
        try:
            await check_publications(bot, bot.db, utcnow())
            await check_reveals(bot, bot.db, utcnow())
            await check_leaderboard_resets(bot, bot.db, utcnow())
        except Exception:
            logger.exception("Batch tick failed")

    @batch_loop.before_loop
    async def before_batch_loop() -> None:
        """Wait for the bot to be ready, then align the first tick to the next round minute."""
        await bot.wait_until_ready()
        now = utcnow()
        await asyncio.sleep(60 - now.second - now.microsecond / 1_000_000)

    async def setup_hook() -> None:
        """Initialize the database, load cogs, and start background tasks."""
        bot.db = await init_db(settings.database_url, Path(settings.migrations_dir))
        logger.info("Database initialized")
        await bot.load_extension("anecbot.cogs")
        logger.info("Cogs loaded")
        batch_loop.start()

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
            command_name = (
                interaction.command.name if interaction.command else "unknown"
            )
            logger.error("Unhandled command error in '%s': %s", command_name, error)
            logger.debug(
                "Command error interaction data (%s): %s",
                command_name,
                interaction.data,
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Une erreur est survenue.",
                    ephemeral=True,
                )

    _original_close = bot.close

    async def close() -> None:
        """Stop background tasks and close the database connection before shutting down."""
        batch_loop.cancel()
        if hasattr(bot, "db"):
            await close_db(bot.db)
        await _original_close()

    bot.close = close

    return bot
