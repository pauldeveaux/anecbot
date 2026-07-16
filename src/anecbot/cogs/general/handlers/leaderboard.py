import discord

from anecbot.features.leaderboard.service import build_leaderboard_embed
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player


async def handle(interaction: discord.Interaction):
    """Show the current leaderboard standings."""
    assert interaction.guild_id is not None
    db = interaction.client.db  # type: ignore[attr-defined]
    entries = await LeaderboardEntry.list(db, guild_id=interaction.guild_id)
    players = {
        p.user_id: p for p in await Player.list(db, guild_id=interaction.guild_id)
    }
    embed = build_leaderboard_embed(entries, players, interaction.guild)
    await interaction.response.send_message(embed=embed, ephemeral=True)
