from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

import aiosqlite
import discord

from anecbot.features.player.service import get_active_targets
from anecbot.features.publisher.views import McqView
from anecbot.features.selector.service import select_pending_anecdote
from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.utils.text import ZERO_WIDTH_SPACE, with_blank_lines
from anecbot.utils.time import (
    discord_timestamp_full_relative,
    next_reveal_datetime,
    parse_days_off,
    utcnow,
)


def build_anecdote_embed(
    anecdote: Anecdote, reveal_at: datetime | None = None
) -> discord.Embed:
    """Build the embed announcing a new anecdote, with an optional reveal date."""
    embed = discord.Embed(title="📝 Nouvelle anecdote !", color=discord.Color.blue())
    embed.add_field(
        name=ZERO_WIDTH_SPACE, value=with_blank_lines(anecdote.content), inline=False
    )
    if reveal_at is not None:
        embed.add_field(
            name="🔍 Révélation prévue",
            value=discord_timestamp_full_relative(reveal_at),
            inline=False,
        )
    return embed


async def publish_next_anecdote(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> Anecdote | None:
    """Publish a weighted-random PENDING anecdote for the guild and transition it to RUNNING."""
    anecdote = await select_pending_anecdote(db, guild_id, utcnow())
    if anecdote is None:
        return None

    guild = await Guild.get(db, guild_id)
    assert guild is not None
    assert guild.channel_id is not None
    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    assert channel is not None

    running = await Anecdote.update(db, anecdote.id, state="RUNNING")

    embed = build_anecdote_embed(running)
    message = await channel.send(embed=embed)

    return await Anecdote.update(db, anecdote.id, anecdote_message_id=message.id)


async def send_empty_queue_warning(
    bot: discord.Client, db: aiosqlite.Connection, guild: Guild
) -> None:
    """Send a one-time warning that there's nothing to publish, unless already sent."""
    if guild.queue_empty_warned:
        return
    assert guild.channel_id is not None
    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    assert channel is not None
    await channel.send("⚠️ Aucune anecdote à publier aujourd'hui.")
    await Guild.update(db, guild.guild_id, queue_empty_warned=1)


async def finish_publishing(
    bot: discord.Client, db: aiosqlite.Connection, guild: Guild, anecdote: Anecdote
) -> Anecdote:
    """Open voting on an already-RUNNING anecdote and transition it to PUBLISHED."""
    discord_guild = bot.get_guild(guild.guild_id)
    assert discord_guild is not None
    assert anecdote.anecdote_message_id is not None
    assert guild.channel_id is not None

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    assert channel is not None
    message = await channel.fetch_message(anecdote.anecdote_message_id)

    published_at = utcnow()
    days_off = parse_days_off(guild.days_off)
    reveal_at = next_reveal_datetime(
        published_at,
        guild.reveal_interval_days,
        guild.reveal_time,
        days_off,
        ZoneInfo(guild.timezone),
    )

    targets = await get_active_targets(db, guild.guild_id)
    view = McqView(anecdote.id, targets, discord_guild)
    embed = build_anecdote_embed(anecdote, reveal_at)
    await message.edit(embed=embed, view=view)

    return await Anecdote.update(
        db, anecdote.id, state="PUBLISHED", published_at=published_at.isoformat()
    )


async def publish_and_open_voting(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> Anecdote | None:
    """Publish the next anecdote with its MCQ, or warn once if the queue is empty."""
    guild = await Guild.get(db, guild_id)
    assert guild is not None

    anecdote = await publish_next_anecdote(bot, db, guild_id)
    if anecdote is None:
        await send_empty_queue_warning(bot, db, guild)
        return None

    return await finish_publishing(bot, db, guild, anecdote)


async def recover_stuck_publications(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> int:
    """Recover anecdotes stuck in RUNNING from a previous crash. Returns the count recovered."""
    guild = await Guild.get(db, guild_id)
    if guild is None or guild.channel_id is None:
        return 0

    stuck = await Anecdote.list(db, guild_id=guild_id, state="RUNNING")
    for anecdote in stuck:
        if anecdote.anecdote_message_id is not None:
            await finish_publishing(bot, db, guild, anecdote)
        else:
            await Anecdote.update(db, anecdote.id, state="PENDING")
    return len(stuck)


async def refresh_published_reveal_dates(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> None:
    """Update the displayed reveal date on every PUBLISHED anecdote's message."""
    guild = await Guild.get(db, guild_id)
    if guild is None or guild.channel_id is None:
        return

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    if channel is None:
        return

    days_off = parse_days_off(guild.days_off)
    tz = ZoneInfo(guild.timezone)
    published = await Anecdote.list(db, guild_id=guild_id, state="PUBLISHED")

    for anecdote in published:
        if anecdote.anecdote_message_id is None or anecdote.published_at is None:
            continue
        published_at = datetime.fromisoformat(anecdote.published_at)
        reveal_at = next_reveal_datetime(
            published_at, guild.reveal_interval_days, guild.reveal_time, days_off, tz
        )
        message = await channel.fetch_message(anecdote.anecdote_message_id)
        embed = build_anecdote_embed(anecdote, reveal_at)
        await message.edit(embed=embed)
