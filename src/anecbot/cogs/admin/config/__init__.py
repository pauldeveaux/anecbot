import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog
from anecbot.cogs.admin.config import (
    channel as channel_config,
    daily_limit,
    days_off,
    interval,
    leaderboard_reset_anchor,
    leaderboard_reset_interval,
    leaderboard_reset_mode,
    publish_time,
    reset,
    reveal_interval,
    reveal_mode,
    reveal_time,
    show,
)
from anecbot.models.enums import LeaderboardResetMode, RevealMode


class ConfigCog(AdminCog):
    """Admin commands for server configuration."""

    config = app_commands.Group(name="config", description="Configuration du bot")

    @config.command(name="channel", description="Définir le channel du quiz")
    @app_commands.describe(channel="Le channel pour les messages du quiz")
    async def config_channel(
        self, interaction: discord.Interaction, channel: discord.TextChannel
    ):
        """Set the quiz channel."""
        await channel_config.handle(interaction, channel)

    @config.command(
        name="interval",
        description="Définir l'intervalle entre les publications (en jours actifs)",
    )
    @app_commands.describe(jours="Nombre de jours actifs entre chaque publication")
    async def config_interval(self, interaction: discord.Interaction, jours: int):
        """Set the publication interval in active days."""
        await interval.handle(interaction, jours)

    @config.command(
        name="publish-time",
        description="Définir l'heure de publication (format HH:MM)",
    )
    @app_commands.describe(heure="Heure de publication au format HH:MM")
    async def config_publish_time(self, interaction: discord.Interaction, heure: str):
        """Set the publication time."""
        await publish_time.handle(interaction, heure)

    @config.command(
        name="days-off",
        description="Définir les jours sans publication",
    )
    @app_commands.describe(
        jours="Numéros de jour séparés par des virgules (0=lundi, 6=dimanche, ex: 5,6)."
        " Laisser vide pour tout effacer."
    )
    async def config_days_off(self, interaction: discord.Interaction, jours: str = ""):
        """Set the days off."""
        await days_off.handle(interaction, jours)

    @config.command(
        name="reveal-mode",
        description="Définir le mode de révélation",
    )
    @app_commands.describe(mode="Quand révéler les anecdotes publiées")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name=label, value=mode.value)
            for mode, label in reveal_mode.MODE_LABELS.items()
        ]
    )
    async def config_reveal_mode(
        self, interaction: discord.Interaction, mode: RevealMode
    ):
        """Set the reveal mode."""
        await reveal_mode.handle(interaction, mode)

    @config.command(
        name="reveal-interval",
        description="Définir le délai avant la révélation (en jours actifs)",
    )
    @app_commands.describe(jours="Nombre de jours actifs avant la révélation")
    async def config_reveal_interval(
        self, interaction: discord.Interaction, jours: int
    ):
        """Set the reveal interval in active days."""
        await reveal_interval.handle(interaction, jours)

    @config.command(
        name="reveal-time",
        description="Définir l'heure de révélation (format HH:MM)",
    )
    @app_commands.describe(heure="Heure de révélation au format HH:MM")
    async def config_reveal_time(self, interaction: discord.Interaction, heure: str):
        """Set the reveal time."""
        await reveal_time.handle(interaction, heure)

    @config.command(
        name="leaderboard-reset-frequency",
        description="Définir la fréquence de reset du leaderboard",
    )
    @app_commands.describe(mode="Fréquence de reset du leaderboard")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name=label, value=mode.value)
            for mode, label in leaderboard_reset_mode.MODE_LABELS.items()
        ]
    )
    async def config_leaderboard_reset_mode(
        self, interaction: discord.Interaction, mode: LeaderboardResetMode
    ):
        """Set the leaderboard reset cadence unit."""
        await leaderboard_reset_mode.handle(interaction, mode)

    @config.command(
        name="leaderboard-every",
        description="Définir tous les combien le leaderboard est réinitialisé",
    )
    @app_commands.describe(
        n="Tous les N (jours/semaines/mois/ans)"
    )
    async def config_leaderboard_reset_interval(
        self, interaction: discord.Interaction, n: int
    ):
        """Set the leaderboard reset interval count."""
        await leaderboard_reset_interval.handle(interaction, n)

    @config.command(
        name="leaderboard-reset-day",
        description="Définir le jour de réinitialisation du leaderboard",
    )
    @app_commands.describe(
        n="weekly : jour de la semaine (0=lundi..6=dimanche) — monthly : jour du "
        "mois (1-29) — yearly : jour de l'année (1-365) — inutilisé en daily"
    )
    async def config_leaderboard_reset_anchor(
        self, interaction: discord.Interaction, n: int
    ):
        """Set the leaderboard reset anchor."""
        await leaderboard_reset_anchor.handle(interaction, n)

    @config.command(
        name="daily-limit",
        description="Définir la limite quotidienne de soumissions par personne",
    )
    @app_commands.describe(
        n="Nombre maximum d'anecdotes par jour et par personne (0 = illimité)"
    )
    async def config_daily_limit(self, interaction: discord.Interaction, n: int):
        """Set the daily submission limit per person."""
        await daily_limit.handle(interaction, n)

    @config.command(
        name="show",
        description="Afficher la configuration actuelle",
    )
    async def config_show(self, interaction: discord.Interaction):
        """Show the current configuration."""
        await show.handle(interaction)

    @config.command(
        name="reset",
        description="Réinitialiser la configuration aux valeurs par défaut",
    )
    async def config_reset(self, interaction: discord.Interaction):
        """Reset configuration to defaults."""
        await reset.handle(interaction)
