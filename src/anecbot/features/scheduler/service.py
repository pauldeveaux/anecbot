from datetime import datetime
from zoneinfo import ZoneInfo

import aiosqlite
import discord

from anecbot.features.next.repository import last_published_at
from anecbot.features.publisher.service import publish_and_open_voting
from anecbot.models.guild import Guild
from anecbot.utils.time import (
    UTC,
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
