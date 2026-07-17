import logging
from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

import aiosqlite
import discord

from anecbot.features.leaderboard.service import award_points, publish_leaderboard
from anecbot.features.revealer.repository import claim_points_award
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.models.vote import Vote
from anecbot.utils.player import display_name
from anecbot.utils.text import ZERO_WIDTH_SPACE, with_blank_lines
from anecbot.utils.time import next_reveal_datetime, parse_days_off

logger = logging.getLogger(__name__)

MAX_VOTES_FIELD_LENGTH = 1000  # stay under Discord's 1024-char embed field value limit


async def get_due_reveals(
    db: aiosqlite.Connection, guild_id: int, now: datetime
) -> list[Anecdote]:
    """Return PUBLISHED anecdotes past their reveal time, plus any REVEALING (mid-crash-recovery)."""
    guild = await Guild.get(db, guild_id)
    if guild is None:
        return []

    days_off = parse_days_off(guild.days_off)
    tz = ZoneInfo(guild.timezone)
    published = await Anecdote.list(
        db, guild_id=guild_id, state=AnecdoteState.PUBLISHED
    )

    due = list(
        await Anecdote.list(db, guild_id=guild_id, state=AnecdoteState.REVEALING)
    )
    for anecdote in published:
        assert anecdote.published_at is not None
        published_at = datetime.fromisoformat(anecdote.published_at)
        reveal_at = next_reveal_datetime(
            published_at, guild.reveal_interval_days, guild.reveal_time, days_off, tz
        )
        if reveal_at <= now:
            due.append(anecdote)
    return due


def build_reveal_embed(
    anecdote: Anecdote,
    votes: list[Vote],
    players: dict[int, Player],
    discord_guild: discord.Guild | None,
) -> discord.Embed:
    """Build the embed showing the anecdote's content, votes summary, and spoiler answer."""
    embed = discord.Embed(title="🔍 Révélation !", color=discord.Color.purple())
    embed.add_field(
        name=ZERO_WIDTH_SPACE, value=with_blank_lines(anecdote.content), inline=False
    )

    if votes:
        lines = []
        for vote in votes:
            voter = players.get(vote.user_id)
            guessed = players.get(vote.voted_for_id)
            voter_name = (
                display_name(voter, discord_guild) if voter else str(vote.user_id)
            )
            guessed_name = (
                display_name(guessed, discord_guild)
                if guessed
                else str(vote.voted_for_id)
            )
            mark = "✅" if vote.voted_for_id == anecdote.target_id else "❌"
            lines.append(f"{mark} {voter_name} → {guessed_name}")
        votes_value = "\n".join(lines)
        if len(votes_value) > MAX_VOTES_FIELD_LENGTH:
            correct = sum(1 for v in votes if v.voted_for_id == anecdote.target_id)
            votes_value = f"✅ {correct}/{len(votes)} ont deviné juste"
    else:
        votes_value = "Aucun vote."

    embed.add_field(name="🗳️ Votes", value=votes_value, inline=False)

    target = players.get(anecdote.target_id)
    target_name = (
        display_name(target, discord_guild) if target else str(anecdote.target_id)
    )
    embed.add_field(name="🎯 Réponse", value=f"|| {target_name} ||", inline=True)

    author = players.get(anecdote.author_id)
    author_name = (
        display_name(author, discord_guild) if author else str(anecdote.author_id)
    )
    embed.add_field(name="✍️ Auteur", value=author_name, inline=True)

    return embed


async def reveal_anecdote(
    bot: discord.Client, db: aiosqlite.Connection, anecdote: Anecdote
) -> Anecdote:
    """Close voting, award points, reply with the reveal, mark REVEALED.

    Split into two checkpoints (PUBLISHED -> REVEALING -> REVEALED) so a crash mid-flight can
    resume safely: award_points is gated by the points_awarded flag (claimed atomically before
    awarding), so a retry after a crash never awards points twice; once REVEALING is reached,
    only the reply-sending step (guarded by reveal_message_id) can still run again.
    """
    guild = await Guild.get(db, anecdote.guild_id)
    assert guild is not None
    assert guild.channel_id is not None
    assert anecdote.anecdote_message_id is not None

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    assert channel is not None
    message = await channel.fetch_message(anecdote.anecdote_message_id)

    votes = await Vote.list(db, anecdote_id=anecdote.id)
    players = {p.user_id: p for p in await Player.list(db, guild_id=anecdote.guild_id)}
    discord_guild = bot.get_guild(anecdote.guild_id)

    if anecdote.state == AnecdoteState.PUBLISHED:
        await message.edit(view=None)
        if await claim_points_award(db, anecdote.id):
            await award_points(
                db, anecdote.guild_id, votes, anecdote.target_id, anecdote.author_id
            )
        anecdote = await Anecdote.update(db, anecdote.id, state=AnecdoteState.REVEALING)
        logger.info("Anecdote %s revealed for guild %s", anecdote.id, anecdote.guild_id)

    if anecdote.reveal_message_id is None:
        embed = build_reveal_embed(anecdote, votes, players, discord_guild)
        reply = await message.reply(embed=embed)
        anecdote = await Anecdote.update(db, anecdote.id, reveal_message_id=reply.id)

    return await Anecdote.update(db, anecdote.id, state=AnecdoteState.REVEALED)


async def reveal_due_anecdotes(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int, now: datetime
) -> list[Anecdote]:
    """Reveal every due anecdote in the guild, including any left REVEALING from a crash."""
    due = await get_due_reveals(db, guild_id, now)
    revealed = [await reveal_anecdote(bot, db, anecdote) for anecdote in due]
    if revealed:
        await publish_leaderboard(bot, db, guild_id)
    return revealed
