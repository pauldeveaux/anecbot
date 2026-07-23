import discord
from discord import app_commands
from discord.ext import commands

from anecbot.cogs.general.handlers import help as help_handler
from anecbot.cogs.general.handlers import leaderboard as leaderboard_handler
from anecbot.cogs.general.handlers import next as next_handler
from anecbot.cogs.general.handlers import rules as rules_handler
from anecbot.cogs.general.handlers import stats as stats_handler
from anecbot.models.enums import LeaderboardKind

LEADERBOARD_CHOICES = [
    app_commands.Choice(name="points", value=LeaderboardKind.POINTS),
    app_commands.Choice(name="accuracy", value=LeaderboardKind.ACCURACY),
    app_commands.Choice(name="published", value=LeaderboardKind.PUBLISHED),
    app_commands.Choice(name="votes", value=LeaderboardKind.VOTES),
]


class GeneralCog(commands.Cog):
    """Public commands available to all users."""

    def __init__(self, bot: commands.Bot):
        """Store the bot instance for use by the command handlers."""
        self.bot = bot

    @app_commands.command(name="help", description="Afficher l'aide du bot")
    async def help(self, interaction: discord.Interaction):
        """Show help guide."""
        await help_handler.handle(interaction)

    @app_commands.command(name="rules", description="Afficher les règles du jeu")
    async def rules(self, interaction: discord.Interaction):
        """Show the game rules."""
        await rules_handler.handle(interaction)

    stats = app_commands.Group(
        name="stats", description="Statistiques du jeu ou d'un joueur"
    )

    @stats.command(name="game", description="Afficher les statistiques du jeu")
    @app_commands.guild_only()
    async def stats_game(self, interaction: discord.Interaction):
        """Show game statistics."""
        await stats_handler.handle(interaction)

    @stats.command(name="player", description="Afficher les statistiques d'un joueur")
    @app_commands.guild_only()
    @app_commands.describe(user="Le joueur à consulter (toi-même si non précisé)")
    async def stats_player(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        """Show a single player's statistics."""
        target = user or interaction.user
        assert isinstance(target, discord.Member)
        await stats_handler.handle_player(interaction, target)

    @app_commands.command(
        name="next", description="Afficher les prochains événements prévus"
    )
    @app_commands.guild_only()
    async def next(self, interaction: discord.Interaction):
        """Show upcoming scheduled events."""
        await next_handler.handle(interaction)

    @app_commands.command(
        name="leaderboard", description="Afficher un classement (points par défaut)"
    )
    @app_commands.guild_only()
    @app_commands.describe(kind="Le classement à afficher (points par défaut)")
    @app_commands.choices(kind=LEADERBOARD_CHOICES)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        kind: app_commands.Choice[str] | None = None,
    ):
        """Show the leaderboard ranked by the given kind, default points."""
        selected = LeaderboardKind(kind.value) if kind else LeaderboardKind.POINTS
        await leaderboard_handler.handle(interaction, selected)


async def setup(bot):
    """Load all general cogs."""
    await bot.add_cog(GeneralCog(bot))
