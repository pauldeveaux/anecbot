import discord
from discord import app_commands
from discord.ext import commands

from anecbot.cogs.general.handlers import help as help_handler
from anecbot.cogs.general.handlers import next as next_handler
from anecbot.cogs.general.handlers import stats as stats_handler


class GeneralCog(commands.Cog):
    """Public commands available to all users."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Afficher l'aide du bot")
    async def help(self, interaction: discord.Interaction):
        """Show help guide."""
        await help_handler.handle(interaction)

    @app_commands.command(name="stats", description="Afficher les statistiques du jeu")
    async def stats(self, interaction: discord.Interaction):
        """Show game statistics."""
        await stats_handler.handle(interaction)

    @app_commands.command(
        name="next", description="Afficher les prochains événements prévus"
    )
    async def next(self, interaction: discord.Interaction):
        """Show upcoming scheduled events."""
        await next_handler.handle(interaction)


async def setup(bot):
    """Load all general cogs."""
    await bot.add_cog(GeneralCog(bot))
