import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.player import Player

logger = logging.getLogger(__name__)


async def handle_suspend(
    interaction: discord.Interaction, user: discord.Member
) -> None:
    """Suspend a player temporarily."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    existing = await Player.get(db, interaction.guild_id, user.id)
    if existing is None:
        await interaction.response.send_message(
            f"❌ {user.mention} n'est pas inscrit(e).",
            ephemeral=True,
        )
        return

    if existing.suspended:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} est déjà suspendu(e).",
            ephemeral=True,
        )
        return

    await Player.update(db, interaction.guild_id, user.id, suspended=1)
    await interaction.response.send_message(
        f"✅ {user.mention} a été suspendu(e).",
        ephemeral=True,
    )

    guild_name = interaction.guild.name if interaction.guild else "le serveur"
    try:
        await user.send(
            f"⏸️ Tu as été mis(e) en pause sur **{guild_name}**. "
            "Tes anecdotes ne seront pas publiées et tu n'apparaîtras pas dans le QCM."
        )
    except discord.Forbidden:
        logger.debug("Cannot DM user %s (DMs disabled)", user.id)


async def handle_unsuspend(
    interaction: discord.Interaction, user: discord.Member
) -> None:
    """Unsuspend a player."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    existing = await Player.get(db, interaction.guild_id, user.id)
    if existing is None:
        await interaction.response.send_message(
            f"❌ {user.mention} n'est pas inscrit(e).",
            ephemeral=True,
        )
        return

    if not existing.suspended:
        await interaction.response.send_message(
            f"ℹ️ {user.mention} n'est pas suspendu(e).",
            ephemeral=True,
        )
        return

    await Player.update(db, interaction.guild_id, user.id, suspended=0)
    await interaction.response.send_message(
        f"✅ {user.mention} n'est plus suspendu(e).",
        ephemeral=True,
    )

    guild_name = interaction.guild.name if interaction.guild else "le serveur"
    try:
        await user.send(
            f"▶️ Tu n'es plus en pause sur **{guild_name}**. "
            "Tes anecdotes peuvent à nouveau être publiées."
        )
    except discord.Forbidden:
        logger.debug("Cannot DM user %s (DMs disabled)", user.id)
