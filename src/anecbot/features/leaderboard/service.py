import logging
from datetime import datetime
from typing import cast

import psycopg
import discord

from anecbot.features.leaderboard.repository import (
    claim_leaderboard_reset,
    count_correct_votes_by_user,
    count_revealed_by_author,
    count_votes_by_user,
    delete_all_entries,
    mark_leaderboard_published,
)
from anecbot.features.leaderboard.views import LeaderboardPlayerButtonsView
from anecbot.features.quality_vote.service import quality_bonus
from anecbot.models.enums import LeaderboardKind
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


def build_ranked_embed(
    title: str, rows: list[tuple[int, str]], empty_message: str
) -> discord.Embed:
    """Build a header embed for a ranked leaderboard, capped to a top-N.

    Each entry's rank/name/value now lives on its own button label (built by
    build_player_entries) rather than as a description line — Discord always renders
    components below the embed, so there's no way to align a button with a specific line of
    embed text. The embed itself only carries the title plus an empty/overflow note.
    """
    shown = rows[:MAX_LEADERBOARD_ENTRIES]
    remaining = len(rows) - len(shown)

    if not rows:
        description = empty_message
    elif remaining > 0:
        description = f"... et {remaining} joueur(s) de plus"
    else:
        description = None

    return discord.Embed(
        title=title, description=description, color=discord.Color.gold()
    )


def build_leaderboard_embed(entries: list[LeaderboardEntry]) -> discord.Embed:
    """Build the header embed for the points leaderboard, capped to a top-N."""
    ranked = sorted(entries, key=lambda e: e.points, reverse=True)
    rows = [(e.user_id, f"{e.points} pt(s)") for e in ranked]
    return build_ranked_embed("🏆 Classement", rows, "Aucun point pour l'instant.")


def build_player_entries(
    rows: list[tuple[int, str]],
    players: dict[int, Player],
    discord_guild: discord.Guild | None,
) -> list[tuple[int, str]]:
    """Build (user_id, label) pairs for each row's button, capped to MAX_LEADERBOARD_ENTRIES.

    label is the full "rank. name — value" line, since the leaderboard's per-row info now
    lives on the buttons themselves rather than in the embed.
    """
    shown = rows[:MAX_LEADERBOARD_ENTRIES]
    entries = []
    for rank, (user_id, value) in enumerate(shown, start=1):
        player = players.get(user_id)
        name = display_name(player, discord_guild) if player else str(user_id)
        label = f"{rank}. {name} — {value}"
        entries.append((user_id, label[:80]))
    return entries


async def get_ranked_entries(
    db: psycopg.AsyncConnection, guild_id: int, kind: LeaderboardKind
) -> list[tuple[int, str]]:
    """Return (user_id, formatted_value) pairs for the given leaderboard kind, ranked descending."""
    if kind == LeaderboardKind.POINTS:
        entries = await LeaderboardEntry.list(db, guild_id=guild_id)
        ranked = sorted(entries, key=lambda e: e.points, reverse=True)
        return [(e.user_id, f"{e.points} pt(s)") for e in ranked]

    if kind == LeaderboardKind.VOTES:
        rows = await count_votes_by_user(db, guild_id)
        return [(user_id, f"{count} vote(s)") for user_id, count in rows]

    if kind == LeaderboardKind.PUBLISHED:
        rows = await count_revealed_by_author(db, guild_id)
        return [(user_id, f"{count} anecdote(s)") for user_id, count in rows]

    votes_cast = dict(await count_votes_by_user(db, guild_id))
    correct_votes = await count_correct_votes_by_user(db, guild_id)
    ranked = sorted(
        (
            (user_id, correct_votes.get(user_id, 0), cast_count)
            for user_id, cast_count in votes_cast.items()
            if cast_count > 0
        ),
        key=lambda row: (row[1] / row[2], row[2]),
        reverse=True,
    )
    return [
        (user_id, f"{correct}/{cast} ({correct / cast * 100:.0f}%)")
        for user_id, correct, cast in ranked
    ]


async def publish_leaderboard(
    bot: discord.Client, db: psycopg.AsyncConnection, guild_id: int
) -> None:
    """Send the current leaderboard standings to the guild's channel with a player picker."""
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
    embed = build_leaderboard_embed(entries)

    rows = [
        (e.user_id, f"{e.points} pt(s)")
        for e in sorted(entries, key=lambda e: e.points, reverse=True)
    ]
    player_entries = build_player_entries(rows, players, discord_guild)
    view = LeaderboardPlayerButtonsView(guild_id, player_entries)

    message = await channel.send(embed=embed, view=view)
    await Guild.update(db, guild_id, leaderboard_message_id=message.id)


async def restore_leaderboard_views(
    bot: discord.Client, db: psycopg.AsyncConnection
) -> None:
    """Re-register the persistent points-leaderboard player buttons for every guild, once on startup.

    LeaderboardPlayerButtonsView instances only live in memory for the process that created
    them, so a restart otherwise leaves the last auto-posted leaderboard message with buttons
    nothing responds to.
    """
    guilds = await Guild.list(db)
    restored = 0
    for guild in guilds:
        if guild.leaderboard_message_id is None:
            continue
        if bot.get_guild(guild.guild_id) is None:
            continue

        entries = await LeaderboardEntry.list(db, guild_id=guild.guild_id)
        if not entries:
            continue

        players = {p.user_id: p for p in await Player.list(db, guild_id=guild.guild_id)}
        discord_guild = bot.get_guild(guild.guild_id)
        rows = [
            (e.user_id, f"{e.points} pt(s)")
            for e in sorted(entries, key=lambda e: e.points, reverse=True)
        ]
        player_entries = build_player_entries(rows, players, discord_guild)
        view = LeaderboardPlayerButtonsView(guild.guild_id, player_entries)
        bot.add_view(view, message_id=guild.leaderboard_message_id)
        restored += 1

    logger.info("Restored %d leaderboard view(s)", restored)


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
