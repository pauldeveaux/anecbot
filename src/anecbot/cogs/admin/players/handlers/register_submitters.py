import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild
from anecbot.models.player import Player

logger = logging.getLogger(__name__)

CUSTOM_ID_PREFIX = "register_submitters"


class RegisterSubmittersView(discord.ui.View):
    """Persistent view with a registration button for submitters."""

    def __init__(self, required_role_id: int | None = None):
        super().__init__(timeout=None)
        custom_id = CUSTOM_ID_PREFIX
        if required_role_id is not None:
            custom_id = f"{CUSTOM_ID_PREFIX}:{required_role_id}"
        self.button = discord.ui.Button(
            label="S'inscrire",
            style=discord.ButtonStyle.success,
            custom_id=custom_id,
        )
        self.button.callback = self._on_click
        self.add_item(self.button)

    async def _on_click(self, interaction: discord.Interaction):
        """Handle registration button click."""
        assert interaction.guild_id is not None
        assert isinstance(interaction.user, discord.Member)

        custom_id = interaction.data.get("custom_id", "") if interaction.data else ""
        required_role_id = _parse_role_id(custom_id)

        if required_role_id is not None:
            has_role = any(r.id == required_role_id for r in interaction.user.roles)
            if not has_role:
                role_mention = f"<@&{required_role_id}>"
                await interaction.response.send_message(
                    f"❌ Tu dois avoir le rôle {role_mention} pour t'inscrire.",
                    ephemeral=True,
                )
                return

        db = get_db(interaction)
        existing = await Player.get(db, interaction.guild_id, interaction.user.id)

        if existing and existing.can_submit:
            await interaction.response.send_message(
                "ℹ️ Tu peux déjà envoyer des anecdotes.",
                ephemeral=True,
            )
            return

        await Guild.upsert(db, interaction.guild_id)
        await Player.upsert(db, interaction.guild_id, interaction.user.id, can_submit=1)
        await interaction.response.send_message(
            "✅ Inscription réussie ! Tu peux maintenant soumettre des anecdotes en DM.",
            ephemeral=True,
        )

        guild_name = interaction.guild.name if interaction.guild else "le serveur"
        try:
            await interaction.user.send(
                f"🎉 Tu peux désormais envoyer des anecdotes pour **{guild_name}** "
                "en m'envoyant un message privé.\n"
                "Tape `/help` si tu veux plus d'infos !"
            )
        except discord.Forbidden:
            logger.debug("Cannot DM user %s (DMs disabled)", interaction.user.id)


def _parse_role_id(custom_id: str) -> int | None:
    """Extract the role ID from a custom_id string."""
    parts = custom_id.split(":")
    if len(parts) == 2:
        return int(parts[1])
    return None


async def handle(interaction: discord.Interaction, role: discord.Role | None = None):
    """Post the submitter registration embed with a persistent button."""
    assert interaction.guild_id is not None
    role_id = role.id if role else None

    description = (
        "Clique sur le bouton ci-dessous pour commencer à envoyer des anecdotes !"
    )
    if role:
        description += f"\n\n⚠️ Rôle requis : {role.mention}"

    embed = discord.Embed(
        title="Inscription — Soumettre des anecdotes",
        description=description,
        color=discord.Color.green(),
    )

    view = RegisterSubmittersView(required_role_id=role_id)
    await interaction.response.send_message(embed=embed, view=view)
