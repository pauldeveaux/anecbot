import logging

import discord

from anecbot.models.player import Player

logger = logging.getLogger(__name__)


def parse_role_id(custom_id: str) -> int | None:
    """Extract the role ID from a custom_id string like 'prefix:ROLE_ID'."""
    parts = custom_id.split(":")
    if len(parts) == 2:
        return int(parts[1])
    return None


def make_custom_id(prefix: str, role_id: int | None) -> str:
    """Build a custom_id with optional role suffix."""
    if role_id is not None:
        return f"{prefix}:{role_id}"
    return prefix


async def check_role(
    interaction: discord.Interaction, required_role_id: int | None
) -> bool:
    """Check if the user has the required role. Sends error if not. Returns True if OK."""
    if required_role_id is None:
        return True
    assert isinstance(interaction.user, discord.Member)
    has_role = any(r.id == required_role_id for r in interaction.user.roles)
    if not has_role:
        await interaction.response.send_message(
            f"❌ Tu dois avoir le rôle <@&{required_role_id}> pour t'inscrire.",
            ephemeral=True,
        )
        return False
    return True


async def check_banned(
    interaction: discord.Interaction, player: Player | None, field: str
) -> bool:
    """Check if the player is banned for the given field. Sends error if banned. Returns True if OK."""
    if player is None:
        return True
    if getattr(player, field, 0):
        await interaction.response.send_message(
            "❌ Tu es banni(e) et ne peux pas t'inscrire.",
            ephemeral=True,
        )
        return False
    return True


async def send_dm(
    user: discord.User | discord.Member, guild_name: str, role_label: str
) -> None:
    """Send a registration confirmation DM. Silently skips if DMs are disabled."""
    try:
        await user.send(
            f"🎉 Tu peux désormais {role_label} pour **{guild_name}** "
            "en m'envoyant un message privé.\n"
            "Tape `/help` si tu veux plus d'infos !"
        )
    except discord.Forbidden:
        logger.debug("Cannot DM user %s (DMs disabled)", user.id)


def build_registration_embed(
    title: str, description: str, role: discord.Role | None
) -> discord.Embed:
    """Build the registration embed with optional role requirement."""
    if role:
        description += f"\n\n⚠️ Rôle requis : {role.mention}"
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green(),
    )
