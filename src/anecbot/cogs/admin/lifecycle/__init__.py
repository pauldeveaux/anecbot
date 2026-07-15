import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog
from anecbot.cogs.admin.lifecycle.handlers import reset as reset_handler
from anecbot.cogs.admin.lifecycle.handlers import start as start_handler
from anecbot.cogs.admin.lifecycle.handlers import stop as stop_handler


class LifecycleCog(AdminCog):
    """Admin commands for game lifecycle."""

    @app_commands.command(name="start", description="Démarrer le jeu")
    async def start(self, interaction: discord.Interaction):
        """Start the quiz game."""
        await start_handler.handle(interaction)

    @app_commands.command(name="stop", description="Mettre le jeu en pause")
    async def stop(self, interaction: discord.Interaction):
        """Stop the quiz game."""
        await stop_handler.handle(interaction)

    @app_commands.command(
        name="reset",
        description="Supprimer toutes les données du serveur (irréversible)",
    )
    async def reset(self, interaction: discord.Interaction):
        """Reset all guild data."""
        await reset_handler.handle(interaction)
