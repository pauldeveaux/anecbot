import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog
from anecbot.cogs.admin.rules.handlers import publish_rules as publish_rules_handler


class RulesCog(AdminCog):
    """Admin commands for publishing the game rules."""

    @app_commands.command(
        name="publish-rules",
        description="Publier les règles du jeu dans le channel configuré",
    )
    async def publish_rules(self, interaction: discord.Interaction):
        """Publish the game rules in the guild's configured channel."""
        await publish_rules_handler.handle(interaction)
