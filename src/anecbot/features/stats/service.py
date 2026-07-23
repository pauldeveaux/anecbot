from dataclasses import dataclass

import discord
import psycopg

from anecbot.features.stats.repository import (
    average_quality_rating,
    count_correct_votes,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry, rank_of
from anecbot.models.player import Player
from anecbot.models.vote import Vote


@dataclass
class GuildStats:
    """Aggregated game statistics for a guild."""

    started: bool
    started_at: str | None
    anecdotes_total: int
    anecdotes_pending: int
    anecdotes_published: int
    anecdotes_revealed: int
    players_submitters: int
    players_targets: int
    players_total: int


async def get_guild_stats(db: psycopg.AsyncConnection, guild_id: int) -> GuildStats:
    """Compute game statistics for a guild."""
    guild = await Guild.get(db, guild_id)

    anecdotes_total = await Anecdote.count(db, guild_id=guild_id)
    anecdotes_pending = await Anecdote.count(
        db, guild_id=guild_id, state=AnecdoteState.PENDING
    )
    anecdotes_published = await Anecdote.count(
        db, guild_id=guild_id, state=AnecdoteState.PUBLISHED
    )
    anecdotes_revealed = await Anecdote.count(
        db, guild_id=guild_id, state=AnecdoteState.REVEALED
    )

    players_total = await Player.count(db, guild_id=guild_id)
    players_submitters = await Player.count(db, guild_id=guild_id, can_submit=1)
    players_targets = await Player.count(db, guild_id=guild_id, can_be_target=1)

    return GuildStats(
        started=bool(guild.started) if guild else False,
        started_at=guild.started_at if guild else None,
        anecdotes_total=anecdotes_total,
        anecdotes_pending=anecdotes_pending,
        anecdotes_published=anecdotes_published,
        anecdotes_revealed=anecdotes_revealed,
        players_submitters=players_submitters,
        players_targets=players_targets,
        players_total=players_total,
    )


@dataclass
class PlayerStats:
    """Aggregated statistics for a single player in a guild."""

    points: int
    rank: int | None
    revealed_count: int
    average_rating: float | None
    votes_cast: int
    correct_votes: int
    accuracy_pct: float | None


async def get_player_stats(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> PlayerStats:
    """Compute a single player's points, rank, anecdote quality, and voting accuracy."""
    entries = await LeaderboardEntry.list(db, guild_id=guild_id)
    entry = next((e for e in entries if e.user_id == user_id), None)

    revealed_count = await Anecdote.count(
        db, guild_id=guild_id, author_id=user_id, state=AnecdoteState.REVEALED
    )
    votes_cast = await Vote.count(db, guild_id=guild_id, user_id=user_id)
    correct_votes = await count_correct_votes(db, guild_id, user_id)

    return PlayerStats(
        points=entry.points if entry else 0,
        rank=rank_of(entries, user_id),
        revealed_count=revealed_count,
        average_rating=await average_quality_rating(db, guild_id, user_id),
        votes_cast=votes_cast,
        correct_votes=correct_votes,
        accuracy_pct=(correct_votes / votes_cast * 100) if votes_cast else None,
    )


def build_player_stats_embed(stats: PlayerStats, name: str) -> discord.Embed:
    """Build an embed with a single player's points, rank, and voting/anecdote statistics."""
    embed = discord.Embed(
        title=f"Statistiques de {name}",
        color=discord.Color.blue(),
    )

    rank_value = f"{stats.rank}ᵉ" if stats.rank is not None else "Non classé"
    embed.add_field(
        name="🏆 Classement",
        value=f"**{stats.points}** pt(s) — {rank_value}",
        inline=False,
    )

    rating_value = (
        f"{stats.average_rating:.1f}/5" if stats.average_rating is not None else "—"
    )
    embed.add_field(
        name="✍️ Anecdotes révélée(s)",
        value=f"Total : {stats.revealed_count}\nNote moyenne : {rating_value}",
        inline=False,
    )

    accuracy_value = (
        f"{stats.accuracy_pct:.0f}%" if stats.accuracy_pct is not None else "—"
    )
    embed.add_field(
        name="🗳️ Votes",
        value=(
            f"Votes : {stats.votes_cast}\n"
            f"Votes corrects : {stats.correct_votes}\n"
            f"Précision : {accuracy_value}"
        ),
        inline=False,
    )

    return embed
