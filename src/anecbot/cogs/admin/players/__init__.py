import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog
from anecbot.cogs.admin.players.handlers import players_list, register_submitters
from anecbot.cogs.admin.players.handlers.register_submitters import (
    RegisterSubmittersView,
)


class PlayersCog(AdminCog):
    """Admin commands for player management."""

    async def cog_load(self):
        """Register persistent views for this cog."""
        self.bot.add_view(RegisterSubmittersView())

    @app_commands.command(
        name="register-submitters",
        description="Poster un message d'inscription pour les rédacteurs d'anecdotes",
    )
    @app_commands.describe(role="Rôle requis pour s'inscrire (optionnel)")
    async def register_submitters(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
    ):
        """Post the submitter registration embed."""
        await register_submitters.handle(interaction, role)

    @app_commands.command(
        name="players",
        description="Lister les joueurs inscrits",
    )
    async def players(self, interaction: discord.Interaction):
        """List registered players."""
        await players_list.handle(interaction)
