import logging
from datetime import datetime
from typing import cast

import psycopg
import discord

from anecbot.features.leaderboard.repository import (
    claim_leaderboard_reset,
    delete_all_entries,
    mark_leaderboard_published,
)
from anecbot.features.quality_vote.service import quality_bonus
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote
from anecbot.utils.player import display_name

logger = logging.getLogger(__name__)

MAX_LEADERBOARD_ENTRIES = 20


async def _add_points(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int, points: int
) -> None:
    """Increment a user's leaderboard points by the given amount, floored at 0."""
    entry = await LeaderboardEntry.get(db, guild_id, user_id)
    current = entry.points if entry else 0
    await LeaderboardEntry.upsert(
        db, guild_id, user_id, points=max(0, current + points)
    )


async def award_points(
    db: psycopg.AsyncConnection,
    guild_id: int,
    votes: list[Vote],
    correct_value: int,
    author_id: int,
    quality_ratings: list[int],
) -> None:
    """Award +1 to each correct voter and a quality-based bonus to the anecdote's author.

    correct_value is a user_id in roster mode or an anecdote_choices.id in custom mode —
    whatever Vote.voted_for_id means for this anecdote. The author's bonus is derived from
    quality_ratings via quality_vote.service.quality_bonus — 0 if no quality votes were cast.
    """
    for vote in votes:
        if vote.voted_for_id == correct_value:
            await _add_points(db, guild_id, vote.user_id, 1)
    await _add_points(db, guild_id, author_id, quality_bonus(quality_ratings))


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
    bot: discord.Client, db: psycopg.AsyncConnection, guild_id: int
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


async def claim_leaderboard_reset_cycle(
    db: psycopg.AsyncConnection, guild_id: int
) -> bool:
    """Atomically claim the leaderboard reset cycle; return False if one is already in progress."""
    return await claim_leaderboard_reset(db, guild_id)


async def mark_leaderboard_reset_published(
    db: psycopg.AsyncConnection, guild_id: int
) -> None:
    """Record that the pre-reset standings message was sent for the current cycle."""
    await mark_leaderboard_published(db, guild_id)


async def reset_leaderboard(
    db: psycopg.AsyncConnection, guild_id: int, now: datetime
) -> None:
    """Clear every leaderboard entry, stamp the reset time, and clear the reset checkpoint."""
    await delete_all_entries(db, guild_id)
    await Guild.upsert(
        db,
        guild_id,
        last_leaderboard_reset_at=now.isoformat(),
        leaderboard_reset_in_progress=0,
        leaderboard_reset_published=0,
    )
    logger.info("Leaderboard reset for guild %s", guild_id)
