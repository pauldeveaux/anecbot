from dataclasses import dataclass

import aiosqlite

from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.models.player import Player


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


async def get_guild_stats(db: aiosqlite.Connection, guild_id: int) -> GuildStats:
    """Compute game statistics for a guild."""
    guild = await Guild.get(db, guild_id)

    anecdotes_total = await Anecdote.count(db, guild_id=guild_id)
    anecdotes_pending = await Anecdote.count(db, guild_id=guild_id, state="PENDING")
    anecdotes_published = await Anecdote.count(db, guild_id=guild_id, state="PUBLISHED")
    anecdotes_revealed = await Anecdote.count(db, guild_id=guild_id, state="REVEALED")

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
