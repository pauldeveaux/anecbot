from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    import aiosqlite

from anecbot.bot import Bot


class AdminCog(commands.Cog):
    """Base class for admin-only cogs with automatic permission checks."""

    def __init__(self, bot: Bot):
        """Store the bot instance for use by subclass command handlers."""
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Reject non-admin users."""
        if not interaction.user.guild_permissions.administrator:  # type: ignore[union-attr]
            raise app_commands.MissingPermissions(["administrator"])
        return True


def get_db(interaction: discord.Interaction) -> "aiosqlite.Connection":
    """Get the database connection from the bot instance."""
    return interaction.client.db  # type: ignore[attr-defined, return-value]
