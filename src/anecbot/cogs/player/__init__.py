import discord
from discord import app_commands
from discord.ext import commands

from anecbot.cogs.player.handlers import leave as leave_handler
from anecbot.cogs.player.handlers import submit as submit_handler
from anecbot.models.enums import PlayerRole

LEAVE_CHOICES = [
    app_commands.Choice(name="rédacteur", value=PlayerRole.SUBMITTER),
    app_commands.Choice(name="cible", value=PlayerRole.TARGET),
    app_commands.Choice(name="tous", value=PlayerRole.ALL),
]


class PlayerCog(commands.Cog):
    """Player-facing commands (DM and guild)."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="leave", description="Se désinscrire d'un rôle ou complètement"
    )
    @app_commands.describe(role="Le rôle à quitter (tout quitter si non précisé)")
    @app_commands.choices(role=LEAVE_CHOICES)
    async def leave(
        self,
        interaction: discord.Interaction,
        role: app_commands.Choice[str] | None = None,
    ):
        """Self-service unregistration."""
        await leave_handler.handle(interaction, role.value if role else PlayerRole.ALL)

    anecdote = app_commands.Group(
        name="anecdote",
        description="Gérer tes anecdotes",
        allowed_contexts=app_commands.AppCommandContext(
            guild=False, dm_channel=True, private_channel=True
        ),
        allowed_installs=app_commands.AppInstallationType(guild=True, user=True),
    )

    @anecdote.command(name="submit", description="Soumettre une anecdote")
    async def anecdote_submit(self, interaction: discord.Interaction):
        """Start the anecdote submission flow in DM."""
        await submit_handler.handle(interaction)


async def setup(bot):
    """Load the player cog."""
    await bot.add_cog(PlayerCog(bot))
