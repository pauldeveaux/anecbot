from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite

from anecbot.features.next.repository import earliest_pending_reveal, last_published_at
from anecbot.features.scheduler.service import is_publication_due
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState, LeaderboardResetMode
from anecbot.models.guild import Guild
from anecbot.utils.time import (
    next_leaderboard_reset_datetime,
    next_publication_datetime,
    next_reveal_datetime,
    parse_days_off,
)


@dataclass
class NextEvents:
    """Upcoming scheduled events for a guild."""

    next_publication: datetime | None
    next_reveal: datetime | None
    next_leaderboard_reset: datetime | None
    leaderboard_reset_hidden: bool
    pending_anecdotes: int
    publication_overdue: bool


async def get_next_events(
    db: aiosqlite.Connection, guild_id: int, now: datetime
) -> NextEvents:
    """Compute next scheduled events for a guild."""
    guild = await Guild.get(db, guild_id)

    if guild is None or not guild.started or guild.channel_id is None:
        return NextEvents(
            next_publication=None,
            next_reveal=None,
            next_leaderboard_reset=None,
            leaderboard_reset_hidden=True,
            pending_anecdotes=0,
            publication_overdue=False,
        )

    pending_count = await Anecdote.count(
        db, guild_id=guild_id, state=AnecdoteState.PENDING
    )
    days_off = parse_days_off(guild.days_off)
    tz = ZoneInfo(guild.timezone)

    last_pub_str = await last_published_at(db, guild_id)
    last_pub = datetime.fromisoformat(last_pub_str) if last_pub_str else None
    next_pub = next_publication_datetime(
        last_pub, guild.interval_days, guild.publish_time, days_off, now, tz
    )
    publication_overdue = pending_count == 0 and is_publication_due(
        last_pub, guild.interval_days, guild.publish_time, days_off, now, tz
    )

    next_rev: datetime | None = None
    earliest_str = await earliest_pending_reveal(db, guild_id)
    if earliest_str:
        earliest = datetime.fromisoformat(earliest_str)
        next_rev = next_reveal_datetime(
            earliest, guild.reveal_interval_days, guild.reveal_time, days_off, tz
        )

    leaderboard_reset_hidden = (
        guild.leaderboard_reset_mode == LeaderboardResetMode.NEVER
    )
    next_reset: datetime | None = None
    if not leaderboard_reset_hidden:
        last_reset = (
            datetime.fromisoformat(guild.last_leaderboard_reset_at)
            if guild.last_leaderboard_reset_at
            else None
        )
        next_reset = next_leaderboard_reset_datetime(
            last_reset,
            guild.leaderboard_reset_mode,
            guild.leaderboard_reset_interval,
            guild.leaderboard_reset_anchor,
            guild.leaderboard_reset_time,
            now,
            tz,
        )

    return NextEvents(
        next_publication=next_pub,
        next_reveal=next_rev,
        next_leaderboard_reset=next_reset,
        leaderboard_reset_hidden=leaderboard_reset_hidden,
        pending_anecdotes=pending_count,
        publication_overdue=publication_overdue,
    )
