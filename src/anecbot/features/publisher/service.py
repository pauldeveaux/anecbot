from typing import cast

import aiosqlite
import discord

from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild


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
