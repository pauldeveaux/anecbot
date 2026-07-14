import discord
from discord import app_commands
from discord.ext import commands

from anecbot.cogs.general import help as help_handler


class GeneralCog(commands.Cog):
    """Public commands available to all users."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Afficher l'aide du bot")
    async def help(self, interaction: discord.Interaction):
        """Show help guide."""
        await help_handler.handle(interaction)


async def setup(bot):
    """Load all general cogs."""
    await bot.add_cog(GeneralCog(bot))
