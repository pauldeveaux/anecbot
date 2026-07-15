from typing import cast

import aiosqlite
import discord

from anecbot.features.player.service import get_active_targets
from anecbot.features.publisher.views import McqView
from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.utils.time import utcnow


async def get_next_pending_anecdote(
    db: aiosqlite.Connection, guild_id: int
) -> Anecdote | None:
    """Return the oldest PENDING anecdote for the guild (FIFO placeholder for ANEC-15)."""
    anecdotes = await Anecdote.list(db, guild_id=guild_id, state="PENDING")
    if not anecdotes:
        return None
    return min(anecdotes, key=lambda a: (a.created_at, a.id))


def build_anecdote_embed(anecdote: Anecdote) -> discord.Embed:
    """Build the embed announcing a new anecdote (content only, no target/author)."""
    return discord.Embed(
        title="📝 Nouvelle anecdote !",
        description=anecdote.content,
        color=discord.Color.blue(),
    )


async def publish_next_anecdote(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> Anecdote | None:
    """Publish the guild's next PENDING anecdote and transition it to RUNNING."""
    anecdote = await get_next_pending_anecdote(db, guild_id)
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

    discord_guild = bot.get_guild(guild_id)
    assert discord_guild is not None
    assert anecdote.anecdote_message_id is not None
    assert guild.channel_id is not None

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    assert channel is not None
    message = await channel.fetch_message(anecdote.anecdote_message_id)

    targets = await get_active_targets(db, guild_id)
    view = McqView(anecdote.id, targets, discord_guild)
    await message.edit(view=view)

    return await Anecdote.update(
        db, anecdote.id, state="PUBLISHED", published_at=utcnow().isoformat()
    )
