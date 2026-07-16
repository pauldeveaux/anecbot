import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.config.leaderboard_reset_format import (
    format_leaderboard_reset_anchor,
)
from anecbot.models.enums import LeaderboardResetMode
from anecbot.models.guild import Guild

logger = logging.getLogger(__name__)

ANCHOR_RANGES: dict[LeaderboardResetMode, tuple[int, int]] = {
    LeaderboardResetMode.WEEKLY: (0, 6),
    LeaderboardResetMode.MONTHLY: (1, 29),
    LeaderboardResetMode.YEARLY: (1, 365),
}


async def handle(interaction: discord.Interaction, n: int):
    """Set the reset anchor, whose meaning depends on the current reset mode."""
    assert interaction.guild_id is not None
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id) or Guild(
        guild_id=interaction.guild_id
    )

    if guild.leaderboard_reset_mode in (
        LeaderboardResetMode.NEVER,
        LeaderboardResetMode.DAILY,
    ):
        await interaction.response.send_message(
            f"❌ Le mode `{guild.leaderboard_reset_mode}` n'utilise pas de jour de reset.",
            ephemeral=True,
        )
        return

    low, high = ANCHOR_RANGES[guild.leaderboard_reset_mode]
    if not (low <= n <= high):
        await interaction.response.send_message(
            f"❌ Pour le mode `{guild.leaderboard_reset_mode}`, le jour de reset doit être "
            f"compris entre {low} et {high}.",
            ephemeral=True,
        )
        return

    await Guild.upsert(db, interaction.guild_id, leaderboard_reset_anchor=n)
    logger.info(
        "Leaderboard reset anchor set to %s for guild %s", n, interaction.guild_id
    )
    label = format_leaderboard_reset_anchor(guild.leaderboard_reset_mode, n)
    await interaction.response.send_message(
        f"✅ Jour de reset du leaderboard configuré : {label}",
        ephemeral=True,
    )
