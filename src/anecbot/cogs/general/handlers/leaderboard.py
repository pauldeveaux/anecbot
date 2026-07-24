import discord

from anecbot.features.leaderboard.service import build_ranked_embed, get_ranked_entries
from anecbot.models.enums import LeaderboardKind
from anecbot.models.player import Player

TITLES = {
    LeaderboardKind.POINTS: "🏆 Classement — Points",
    LeaderboardKind.ACCURACY: "🎯 Classement — Précision",
    LeaderboardKind.PUBLISHED: "✍️ Classement — Anecdotes révélées",
    LeaderboardKind.VOTES: "🗳️ Classement — Votes",
}

EMPTY_MESSAGES = {
    LeaderboardKind.POINTS: "Aucun point pour l'instant.",
    LeaderboardKind.ACCURACY: "Aucun vote pour l'instant.",
    LeaderboardKind.PUBLISHED: "Aucune anecdote révélée pour l'instant.",
    LeaderboardKind.VOTES: "Aucun vote pour l'instant.",
}


async def handle(interaction: discord.Interaction, kind: LeaderboardKind):
    """Show the leaderboard ranked by the given kind."""
    assert interaction.guild_id is not None
    db = interaction.client.db  # type: ignore[attr-defined]
    rows = await get_ranked_entries(db, interaction.guild_id, kind)
    players = {
        p.user_id: p for p in await Player.list(db, guild_id=interaction.guild_id)
    }
    embed = build_ranked_embed(
        TITLES[kind], rows, EMPTY_MESSAGES[kind], players, interaction.guild
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
