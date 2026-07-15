import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.enums import PlayerRole
from anecbot.models.guild import Guild
from anecbot.models.player import Player

logger = logging.getLogger(__name__)


async def handle_ban(
    interaction: discord.Interaction, user: discord.Member, role: str | None = None
) -> None:
    """Ban a player from registering."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    await Guild.upsert(db, interaction.guild_id)

    kwargs: dict[str, object] = {}
    if role in (PlayerRole.SUBMITTER, None):
        kwargs["banned_submit"] = 1
        kwargs["can_submit"] = 0
    if role in (PlayerRole.TARGET, None):
        kwargs["banned_target"] = 1
        kwargs["can_be_target"] = 0

    await Player.upsert(db, interaction.guild_id, user.id, **kwargs)

    if role is None:
        label = "totalement"
    elif role == PlayerRole.SUBMITTER:
        label = "en tant que rédacteur"
    else:
        label = "en tant que cible"

    await interaction.response.send_message(
        f"✅ {user.mention} a été banni(e) {label}.",
        ephemeral=True,
    )

    guild_name = interaction.guild.name if interaction.guild else "le serveur"
    try:
        await user.send(f"🚫 Tu as été banni(e) {label} sur **{guild_name}**.")
    except discord.Forbidden:
        logger.debug("Cannot DM user %s (DMs disabled)", user.id)


async def handle_unban(
    interaction: discord.Interaction, user: discord.Member, role: str | None = None
) -> None:
    """Unban a player."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    existing = await Player.get(db, interaction.guild_id, user.id)
    if existing is None:
        await interaction.response.send_message(
            f"❌ {user.mention} n'est pas inscrit(e).",
            ephemeral=True,
        )
        return

    kwargs: dict[str, object] = {}
    if role in (PlayerRole.SUBMITTER, None):
        kwargs["banned_submit"] = 0
    if role in (PlayerRole.TARGET, None):
        kwargs["banned_target"] = 0

    await Player.update(db, interaction.guild_id, user.id, **kwargs)

    if role is None:
        label = "totalement"
    elif role == PlayerRole.SUBMITTER:
        label = "en tant que rédacteur"
    else:
        label = "en tant que cible"

    await interaction.response.send_message(
        f"✅ {user.mention} a été débanni(e) {label}.",
        ephemeral=True,
    )

    guild_name = interaction.guild.name if interaction.guild else "le serveur"
    try:
        await user.send(f"✅ Tu as été débanni(e) {label} sur **{guild_name}**.")
    except discord.Forbidden:
        logger.debug("Cannot DM user %s (DMs disabled)", user.id)
