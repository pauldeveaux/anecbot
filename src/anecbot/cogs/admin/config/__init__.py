import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog
from anecbot.cogs.admin.config import channel as channel_handler
from anecbot.cogs.admin.config import interval as interval_handler
from anecbot.cogs.admin.config import publish_time as publish_time_handler
from anecbot.cogs.admin.config import reset as reset_handler


class ConfigCog(AdminCog):
    """Admin commands for server configuration."""

    config = app_commands.Group(name="config", description="Configuration du bot")

    @config.command(name="channel", description="Définir le channel du quiz")
    @app_commands.describe(channel="Le channel pour les messages du quiz")
    async def config_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Set the quiz channel."""
        await channel_handler.handle(interaction, channel)

    @config.command(
        name="interval",
        description="Définir l'intervalle entre les publications (en jours actifs)",
    )
    @app_commands.describe(jours="Nombre de jours actifs entre chaque publication")
    async def config_interval(self, interaction: discord.Interaction, jours: int):
        """Set the publication interval in active days."""
        await interval_handler.handle(interaction, jours)

    @config.command(
        name="publish-time",
        description="Définir l'heure de publication (format HH:MM)",
    )
    @app_commands.describe(heure="Heure de publication au format HH:MM")
    async def config_publish_time(self, interaction: discord.Interaction, heure: str):
        """Set the publication time."""
        await publish_time_handler.handle(interaction, heure)

    @config.command(
        name="reset",
        description="Réinitialiser la configuration aux valeurs par défaut",
    )
    async def config_reset(self, interaction: discord.Interaction):
        """Reset configuration to defaults."""
        await reset_handler.handle(interaction)
