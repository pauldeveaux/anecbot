import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.config.handlers.leaderboard_reset_format import (
    format_leaderboard_reset_interval,
)
from anecbot.models.guild import Guild


async def handle(interaction: discord.Interaction, n: int):
    """Set the number of cadence units between leaderboard resets."""
    assert interaction.guild_id is not None
    if n < 1:
        await interaction.response.send_message(
            "❌ L'intervalle doit être 1 ou plus.",
            ephemeral=True,
        )
        return
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id) or Guild(
        guild_id=interaction.guild_id
    )
    await Guild.upsert(db, interaction.guild_id, leaderboard_reset_interval=n)
    label = format_leaderboard_reset_interval(guild.leaderboard_reset_mode, n)
    await interaction.response.send_message(
        f"✅ Reset du leaderboard configuré : {label}",
        ephemeral=True,
    )
