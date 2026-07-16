import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.anecdote.service import (
    discard_pending_anecdotes,
    player_has_anecdotes,
)
from anecbot.models.enums import PlayerRole
from anecbot.models.player import Player

logger = logging.getLogger(__name__)


async def handle(
    interaction: discord.Interaction, user: discord.Member, role: str | None = None
) -> None:
    """Admin-unregister a user from a role or entirely."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    existing = await Player.get(db, interaction.guild_id, user.id)
    if existing is None:
        await interaction.response.send_message(
            f"❌ {user.mention} n'est pas inscrit(e).",
            ephemeral=True,
        )
        return

    guild_name = interaction.guild.name if interaction.guild else "le serveur"

    if role is None:
        has_ban = existing.banned_submit or existing.banned_target
        await Player.update(
            db, interaction.guild_id, user.id, can_submit=0, can_be_target=0
        )
        if not has_ban:
            await discard_pending_anecdotes(db, interaction.guild_id, user.id)
            if not await player_has_anecdotes(db, interaction.guild_id, user.id):
                await Player.delete(db, interaction.guild_id, user.id)

        if has_ban:
            msg = f"✅ Rôles retirés pour {user.mention} (le ban reste actif)."
        else:
            msg = f"✅ {user.mention} a été désinscrit(e)."
        logger.info("User %s unregistered in guild %s", user.id, interaction.guild_id)
        await interaction.response.send_message(msg, ephemeral=True)
        await _notify_user(user, guild_name, "désinscrit(e)")
        return

    if role == PlayerRole.SUBMITTER:
        await Player.update(db, interaction.guild_id, user.id, can_submit=0)
        label = "rédacteur"
    else:
        await Player.update(db, interaction.guild_id, user.id, can_be_target=0)
        label = "cible"

    updated = await Player.get(db, interaction.guild_id, user.id)
    if (
        updated
        and not updated.can_submit
        and not updated.can_be_target
        and not updated.banned_submit
        and not updated.banned_target
    ):
        await discard_pending_anecdotes(db, interaction.guild_id, user.id)
        if not await player_has_anecdotes(db, interaction.guild_id, user.id):
            await Player.delete(db, interaction.guild_id, user.id)

    logger.info(
        "User %s unregistered from role %s in guild %s",
        user.id,
        label,
        interaction.guild_id,
    )
    await interaction.response.send_message(
        f"✅ {user.mention} n'est plus {label}.",
        ephemeral=True,
    )
    await _notify_user(user, guild_name, f"retiré(e) du rôle {label}")


async def _notify_user(user: discord.Member, guild_name: str, action: str) -> None:
    """Notify a user by DM that they were unregistered."""
    try:
        await user.send(f"ℹ️ Tu as été {action} sur **{guild_name}**.")
    except discord.Forbidden:
        logger.debug("Cannot DM user %s (DMs disabled)", user.id)
