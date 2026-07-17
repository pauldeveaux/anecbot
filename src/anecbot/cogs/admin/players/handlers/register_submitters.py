import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.players.handlers.registration import (
    build_registration_embed,
    check_banned,
    check_role,
    make_custom_id,
    parse_role_id,
    send_dm,
)
from anecbot.models.guild import Guild
from anecbot.models.player import Player

logger = logging.getLogger(__name__)

CUSTOM_ID_PREFIX = "register_submitters"


class RegisterSubmittersView(discord.ui.View):
    """Persistent view with a registration button for submitters."""

    def __init__(self, required_role_id: int | None = None):
        """Build the persistent registration button, encoding the required role in its custom_id."""
        super().__init__(timeout=None)
        self.button = discord.ui.Button(
            label="S'inscrire",
            style=discord.ButtonStyle.success,
            custom_id=make_custom_id(CUSTOM_ID_PREFIX, required_role_id),
        )
        self.button.callback = self._on_click
        self.add_item(self.button)

    async def _on_click(self, interaction: discord.Interaction):
        """Handle registration button click."""
        assert interaction.guild_id is not None
        assert isinstance(interaction.user, discord.Member)

        custom_id = interaction.data.get("custom_id", "") if interaction.data else ""
        required_role_id = parse_role_id(custom_id)

        if not await check_role(interaction, required_role_id):
            return

        db = get_db(interaction)
        existing = await Player.get(db, interaction.guild_id, interaction.user.id)

        if not await check_banned(interaction, existing, "banned_submit"):
            return

        if existing and existing.can_submit:
            await interaction.response.send_message(
                "ℹ️ Tu peux déjà envoyer des anecdotes.",
                ephemeral=True,
            )
            return

        await Guild.upsert(db, interaction.guild_id)
        await Player.upsert(db, interaction.guild_id, interaction.user.id, can_submit=1)
        logger.info(
            "User %s self-registered as submitter in guild %s",
            interaction.user.id,
            interaction.guild_id,
        )
        await interaction.response.send_message(
            "✅ Inscription réussie ! Tu peux maintenant soumettre des anecdotes en DM.",
            ephemeral=True,
        )

        guild_name = interaction.guild.name if interaction.guild else "le serveur"
        await send_dm(interaction.user, guild_name, "envoyer des anecdotes")


async def handle(interaction: discord.Interaction, role: discord.Role | None = None):
    """Post the submitter registration embed with a persistent button."""
    assert interaction.guild_id is not None
    embed = build_registration_embed(
        title="Inscription — Soumettre des anecdotes",
        description="Clique sur le bouton ci-dessous pour commencer à envoyer des anecdotes !",
        role=role,
    )
    view = RegisterSubmittersView(required_role_id=role.id if role else None)
    await interaction.response.send_message(embed=embed, view=view)
