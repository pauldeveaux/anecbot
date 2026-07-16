from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import aiosqlite
import discord

from anecbot.features.leaderboard.service import publish_leaderboard, reset_leaderboard
from anecbot.features.next.repository import last_published_at
from anecbot.features.publisher.service import publish_and_open_voting
from anecbot.features.revealer.service import reveal_due_anecdotes
from anecbot.models.enums import LeaderboardResetMode
from anecbot.models.guild import Guild
from anecbot.utils.time import (
    UTC,
    add_months,
    clamped_month_date,
    next_active_day,
    parse_days_off,
    parse_time,
    to_local,
)


def is_publication_due(
    last_published: datetime | None,
    interval_days: int,
    publish_time: str,
    days_off: set[int],
    now: datetime,
    tz: ZoneInfo = UTC,
) -> bool:
    """Return whether a publication is due now, given the last one (or None if never)."""
    local_now = to_local(now, tz)
    local_last = to_local(last_published, tz) if last_published is not None else None
    target_time = parse_time(publish_time)
    if local_last is None:
        today = local_now.date()
        return today.weekday() not in days_off and local_now.time() >= target_time
    target_date = next_active_day(local_last.date(), interval_days, days_off)
    target_dt = datetime.combine(target_date, target_time)
    return local_now >= target_dt


async def check_publication_for_guild(
    bot: discord.Client, db: aiosqlite.Connection, guild: Guild, now: datetime
) -> bool:
    """Trigger publication for the guild if due. Returns whether it was triggered."""
    if not guild.started or guild.channel_id is None:
        return False

    days_off = parse_days_off(guild.days_off)
    last_pub_str = await last_published_at(db, guild.guild_id)
    last_pub = datetime.fromisoformat(last_pub_str) if last_pub_str else None
    tz = ZoneInfo(guild.timezone)

    if not is_publication_due(
        last_pub, guild.interval_days, guild.publish_time, days_off, now, tz
    ):
        return False

    await publish_and_open_voting(bot, db, guild.guild_id)
    return True


async def check_publications(
    bot: discord.Client, db: aiosqlite.Connection, now: datetime
) -> int:
    """Check every started guild and trigger publication where due. Returns the count triggered."""
    guilds = await Guild.list(db, started=1)
    triggered = 0
    for guild in guilds:
        if await check_publication_for_guild(bot, db, guild, now):
            triggered += 1
    return triggered


async def check_reveal_for_guild(
    bot: discord.Client, db: aiosqlite.Connection, guild: Guild, now: datetime
) -> int:
    """Reveal every due anecdote for the guild if it's active. Returns the count revealed."""
    if not guild.started or guild.channel_id is None:
        return 0
    revealed = await reveal_due_anecdotes(bot, db, guild.guild_id, now)
    return len(revealed)


async def check_reveals(
    bot: discord.Client, db: aiosqlite.Connection, now: datetime
) -> int:
    """Check every started guild and reveal anecdotes where due. Returns the total revealed."""
    guilds = await Guild.list(db, started=1)
    total = 0
    for guild in guilds:
        total += await check_reveal_for_guild(bot, db, guild, now)
    return total


def is_leaderboard_reset_due(
    last_reset: datetime | None,
    mode: LeaderboardResetMode,
    interval: int,
    anchor: int | None,
    now: datetime,
    tz: ZoneInfo = UTC,
) -> bool:
    """Return whether the leaderboard reset is due now, given the last reset (or None if never)."""
    if mode == LeaderboardResetMode.NEVER:
        return False

    local_now = to_local(now, tz)
    local_last = to_local(last_reset, tz) if last_reset is not None else None

    if mode == LeaderboardResetMode.DAILY:
        if local_last is None:
            return True
        return local_now >= local_last + timedelta(days=interval)

    if mode == LeaderboardResetMode.WEEKLY:
        assert anchor is not None
        if local_last is None:
            current_monday = local_now.date() - timedelta(days=local_now.weekday())
            target_date = current_monday + timedelta(days=anchor)
            return local_now.date() >= target_date
        return local_now >= local_last + timedelta(weeks=interval)

    if mode == LeaderboardResetMode.MONTHLY:
        assert anchor is not None
        if local_last is None:
            target_date = clamped_month_date(local_now.year, local_now.month, anchor)
        else:
            year, month = add_months(local_last.year, local_last.month, interval)
            target_date = clamped_month_date(year, month, anchor)
        return local_now.date() >= target_date

    assert anchor is not None
    if local_last is None:
        target_date = date(local_now.year, 1, 1) + timedelta(days=anchor - 1)
    else:
        target_date = date(local_last.year + interval, 1, 1) + timedelta(
            days=anchor - 1
        )
    return local_now.date() >= target_date


async def check_leaderboard_reset_for_guild(
    bot: discord.Client, db: aiosqlite.Connection, guild: Guild, now: datetime
) -> bool:
    """Publish final standings and reset the leaderboard for the guild if due."""
    if not guild.started or guild.channel_id is None:
        return False

    last_reset = (
        datetime.fromisoformat(guild.last_leaderboard_reset_at)
        if guild.last_leaderboard_reset_at
        else None
    )
    tz = ZoneInfo(guild.timezone)

    if not is_leaderboard_reset_due(
        last_reset,
        guild.leaderboard_reset_mode,
        guild.leaderboard_reset_interval,
        guild.leaderboard_reset_anchor,
        now,
        tz,
    ):
        return False

    await publish_leaderboard(bot, db, guild.guild_id)
    await reset_leaderboard(db, guild.guild_id, now)
    return True


async def check_leaderboard_resets(
    bot: discord.Client, db: aiosqlite.Connection, now: datetime
) -> int:
    """Check every started guild and reset the leaderboard where due. Returns the count triggered."""
    guilds = await Guild.list(db, started=1)
    triggered = 0
    for guild in guilds:
        if await check_leaderboard_reset_for_guild(bot, db, guild, now):
            triggered += 1
    return triggered
