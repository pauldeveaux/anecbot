import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog
from anecbot.cogs.admin.players.handlers import (
    ban,
    players_list,
    register,
    register_submitters,
    register_targets,
    suspend,
    unregister,
)
from anecbot.cogs.admin.players.handlers.register_submitters import (
    RegisterSubmittersView,
)
from anecbot.cogs.admin.players.handlers.register_targets import RegisterTargetsView
from anecbot.models.enums import PlayerFilter, PlayerRole

ROLE_CHOICES = [
    app_commands.Choice(name="rédacteur", value=PlayerRole.SUBMITTER),
    app_commands.Choice(name="cible", value=PlayerRole.TARGET),
]

ROLE_CHOICES_WITH_ALL = [
    *ROLE_CHOICES,
    app_commands.Choice(name="tous", value=PlayerRole.ALL),
]

FILTER_CHOICES = [
    app_commands.Choice(name="rédacteurs", value=PlayerFilter.SUBMITTER),
    app_commands.Choice(name="cibles", value=PlayerFilter.TARGET),
    app_commands.Choice(name="bannis", value=PlayerFilter.BANNED),
]


class PlayersCog(AdminCog):
    """Admin commands for player management."""

    async def cog_load(self):
        """Register persistent views for this cog."""
        self.bot.add_view(RegisterSubmittersView())
        self.bot.add_view(RegisterTargetsView())

    @app_commands.command(
        name="register-submitters",
        description="Ouvrir les inscriptions pour écrire des anecdotes",
    )
    @app_commands.describe(role="Rôle requis pour s'inscrire (optionnel)")
    async def register_submitters_cmd(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
    ):
        """Post the submitter registration embed."""
        await register_submitters.handle(interaction, role)

    @app_commands.command(
        name="register-targets",
        description="Ouvrir les inscriptions pour être cible",
    )
    @app_commands.describe(role="Rôle requis pour s'inscrire (optionnel)")
    async def register_targets_cmd(
        self,
        interaction: discord.Interaction,
        role: discord.Role | None = None,
    ):
        """Post the target registration embed."""
        await register_targets.handle(interaction, role)

    @app_commands.command(
        name="register",
        description="Inscrire un joueur directement",
    )
    @app_commands.describe(
        user="Le joueur à inscrire",
        role="Le rôle à attribuer",
    )
    @app_commands.choices(role=ROLE_CHOICES_WITH_ALL)
    async def register_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: app_commands.Choice[str],
    ):
        """Admin-register a user."""
        await register.handle(interaction, user, role.value)

    @app_commands.command(
        name="unregister",
        description="Désinscrire un joueur",
    )
    @app_commands.describe(
        user="Le joueur à désinscrire",
        role="Le rôle à retirer (tous si non précisé)",
    )
    @app_commands.choices(role=ROLE_CHOICES)
    async def unregister_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: app_commands.Choice[str] | None = None,
    ):
        """Admin-unregister a user."""
        await unregister.handle(interaction, user, role.value if role else None)

    @app_commands.command(
        name="suspend",
        description="Mettre un joueur en pause (exclu des publications et du QCM)",
    )
    @app_commands.describe(user="Le joueur à suspendre")
    async def suspend_cmd(self, interaction: discord.Interaction, user: discord.Member):
        """Suspend a player."""
        await suspend.handle_suspend(interaction, user)

    @app_commands.command(
        name="unsuspend",
        description="Réactiver un joueur mis en pause",
    )
    @app_commands.describe(user="Le joueur à réactiver")
    async def unsuspend_cmd(
        self, interaction: discord.Interaction, user: discord.Member
    ):
        """Unsuspend a player."""
        await suspend.handle_unsuspend(interaction, user)

    @app_commands.command(
        name="ban",
        description="Bannir un joueur (ne peut plus s'inscrire)",
    )
    @app_commands.describe(
        user="Le joueur à bannir",
        role="Le rôle à bannir (tous si non précisé)",
    )
    @app_commands.choices(role=ROLE_CHOICES)
    async def ban_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: app_commands.Choice[str] | None = None,
    ):
        """Ban a player."""
        await ban.handle_ban(interaction, user, role.value if role else None)

    @app_commands.command(
        name="unban",
        description="Débannir un joueur",
    )
    @app_commands.describe(
        user="Le joueur à débannir",
        role="Le rôle à débannir (tous si non précisé)",
    )
    @app_commands.choices(role=ROLE_CHOICES)
    async def unban_cmd(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        role: app_commands.Choice[str] | None = None,
    ):
        """Unban a player."""
        await ban.handle_unban(interaction, user, role.value if role else None)

    @app_commands.command(
        name="players",
        description="Lister les joueurs inscrits",
    )
    @app_commands.describe(
        filtre="Filtrer par catégorie (tous par défaut)",
    )
    @app_commands.choices(filtre=FILTER_CHOICES)
    async def players_cmd(
        self,
        interaction: discord.Interaction,
        filtre: app_commands.Choice[str] | None = None,
    ):
        """List players with optional filter."""
        await players_list.handle(interaction, filtre.value if filtre else None)
