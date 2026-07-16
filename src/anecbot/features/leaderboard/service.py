from datetime import datetime
from typing import cast

import aiosqlite
import discord

from anecbot.features.leaderboard.repository import delete_all_entries
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote
from anecbot.utils.player import display_name

MAX_LEADERBOARD_ENTRIES = 20


async def _add_points(
    db: aiosqlite.Connection, guild_id: int, user_id: int, points: int
) -> None:
    """Increment a user's leaderboard points by the given amount."""
    entry = await LeaderboardEntry.get(db, guild_id, user_id)
    current = entry.points if entry else 0
    await LeaderboardEntry.upsert(db, guild_id, user_id, points=current + points)


async def award_points(
    db: aiosqlite.Connection,
    guild_id: int,
    votes: list[Vote],
    target_id: int,
    author_id: int,
) -> None:
    """Award +1 to each correct voter and a flat +1 to the anecdote's author."""
    for vote in votes:
        if vote.voted_for_id == target_id:
            await _add_points(db, guild_id, vote.user_id, 1)
    await _add_points(db, guild_id, author_id, 1)


def build_leaderboard_embed(
    entries: list[LeaderboardEntry],
    players: dict[int, Player],
    discord_guild: discord.Guild | None,
) -> discord.Embed:
    """Build the embed showing ranked leaderboard standings, capped to a top-N."""
    ranked = sorted(entries, key=lambda e: e.points, reverse=True)
    shown = ranked[:MAX_LEADERBOARD_ENTRIES]

    lines = []
    for rank, entry in enumerate(shown, start=1):
        player = players.get(entry.user_id)
        name = display_name(player, discord_guild) if player else str(entry.user_id)
        lines.append(f"**{rank}.** {name} — {entry.points} pt(s)")

    remaining = len(ranked) - len(shown)
    if remaining > 0:
        lines.append(f"... et {remaining} joueur(s) de plus")

    return discord.Embed(
        title="🏆 Classement",
        description="\n".join(lines) if lines else "Aucun point pour l'instant.",
        color=discord.Color.gold(),
    )


async def publish_leaderboard(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> None:
    """Send the current leaderboard standings to the guild's channel."""
    guild = await Guild.get(db, guild_id)
    if guild is None or guild.channel_id is None:
        return

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    if channel is None:
        return

    entries = await LeaderboardEntry.list(db, guild_id=guild_id)
    if not entries:
        return

    players = {p.user_id: p for p in await Player.list(db, guild_id=guild_id)}
    discord_guild = bot.get_guild(guild_id)
    embed = build_leaderboard_embed(entries, players, discord_guild)
    await channel.send(embed=embed)


async def reset_leaderboard(
    db: aiosqlite.Connection, guild_id: int, now: datetime
) -> None:
    """Clear every leaderboard entry for the guild and stamp the reset time."""
    await delete_all_entries(db, guild_id)
    await Guild.upsert(db, guild_id, last_leaderboard_reset_at=now.isoformat())
