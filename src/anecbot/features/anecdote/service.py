import logging
from collections.abc import Sequence

import discord
import psycopg

from anecbot.features.anecdote.repository import (
    count_created_today,
    delete_pending_by_author,
    has_any_for_user,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.anecdote_choice import AnecdoteChoice
from anecbot.models.enums import AnecdoteState
from anecbot.models.guild import Guild

logger = logging.getLogger(__name__)

# States a not-yet-REVEALED anecdote can be in — the only ones where a stale migration-backfilled
# label (a raw user id) can still surface to players (PUBLISHED) or is worth fixing before it does
# (PENDING/RUNNING/REVEALING).
_NOT_REVEALED_STATES = (
    AnecdoteState.PENDING,
    AnecdoteState.RUNNING,
    AnecdoteState.PUBLISHED,
    AnecdoteState.REVEALING,
)


async def daily_limit_status(
    db: psycopg.AsyncConnection, guild_id: int, author_id: int
) -> tuple[bool, int]:
    """Return (reached, limit) for the author's daily submission limit."""
    guild = await Guild.get(db, guild_id)
    assert guild is not None
    if guild.daily_limit == 0:
        return False, 0
    count = await count_created_today(db, guild_id, author_id)
    return count >= guild.daily_limit, guild.daily_limit


async def create_anecdote(
    db: psycopg.AsyncConnection,
    guild_id: int,
    author_id: int,
    content: str,
    *,
    target_label: str,
    choice_labels: Sequence[str],
) -> Anecdote:
    """Create a new anecdote in PENDING state with its MCQ choices, clear the empty-queue flag.

    target_label and choice_labels are always plain text — resolved from the guild's roster at
    submission time if the author picked a registered player, or typed freely for a custom
    target — so there's a single representation regardless of how the target was chosen.
    """
    anecdote = await Anecdote.create(
        db, guild_id=guild_id, author_id=author_id, content=content
    )
    await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label=target_label, is_correct=1
    )
    for label in choice_labels:
        await AnecdoteChoice.create(
            db, anecdote_id=anecdote.id, label=label, is_correct=0
        )
    await Guild.update(db, guild_id, queue_empty_warned=0)
    logger.info("Anecdote %s created for guild %s", anecdote.id, guild_id)
    return anecdote


async def backfill_migrated_target_labels(
    bot: discord.Client, db: psycopg.AsyncConnection
) -> int:
    """Resolve migration-backfilled numeric choice labels to real display names, once.

    migrations/0002_anecdote_choices.sql backfilled anecdote_choices from the dropped target_id
    column using the raw user id as text, since Discord display names aren't reachable from SQL.
    Once the bot is ready and has its member cache, replace any resolvable purely-numeric label
    on a not-yet-REVEALED anecdote with the member's current display name, so publish/reveal show
    names instead of ids. Safe to call on every startup: once a label is resolved it's no longer
    numeric, so there's nothing left to redo on later runs.
    """
    resolved = 0
    for state in _NOT_REVEALED_STATES:
        for anecdote in await Anecdote.list(db, state=state):
            guild = bot.get_guild(anecdote.guild_id)
            if guild is None:
                continue
            for choice in await get_choices(db, anecdote.id):
                if not choice.label.isdigit():
                    continue
                member = guild.get_member(int(choice.label))
                if member is None:
                    continue
                await AnecdoteChoice.update(db, choice.id, label=member.display_name)
                resolved += 1
    if resolved:
        logger.info("Resolved %d migration-backfilled choice label(s)", resolved)
    return resolved


async def get_choices(
    db: psycopg.AsyncConnection, anecdote_id: int
) -> list[AnecdoteChoice]:
    """Return all MCQ choices for an anecdote (the target and its wrong choices)."""
    return await AnecdoteChoice.list(db, anecdote_id=anecdote_id)


async def get_correct_choice(
    db: psycopg.AsyncConnection, anecdote_id: int
) -> AnecdoteChoice:
    """Return the choice that is the anecdote's actual target."""
    choices = await get_choices(db, anecdote_id)
    return next(c for c in choices if c.is_correct)


async def get_pending_by_author(
    db: psycopg.AsyncConnection, guild_id: int, author_id: int
) -> list[Anecdote]:
    """Return the author's PENDING anecdotes in the guild, most recent first."""
    anecdotes = await Anecdote.list(
        db, guild_id=guild_id, author_id=author_id, state=AnecdoteState.PENDING
    )
    return sorted(anecdotes, key=lambda a: (a.created_at, a.id), reverse=True)


async def get_owned_pending_anecdote(
    db: psycopg.AsyncConnection, anecdote_id: int, author_id: int
) -> Anecdote | None:
    """Return the anecdote if it exists, belongs to author_id, and is still PENDING."""
    anecdote = await Anecdote.get(db, anecdote_id)
    if (
        anecdote is None
        or anecdote.author_id != author_id
        or anecdote.state != AnecdoteState.PENDING
    ):
        return None
    return anecdote


async def update_content(
    db: psycopg.AsyncConnection, anecdote_id: int, content: str
) -> Anecdote:
    """Update a PENDING anecdote's content."""
    return await Anecdote.update(db, anecdote_id, content=content)


async def delete_anecdote(db: psycopg.AsyncConnection, anecdote_id: int) -> bool:
    """Delete an anecdote, return True if it existed."""
    return await Anecdote.delete(db, anecdote_id)


async def player_has_anecdotes(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> bool:
    """Return whether the player has authored any anecdote in the guild."""
    return await has_any_for_user(db, guild_id, user_id)


async def discard_pending_anecdotes(
    db: psycopg.AsyncConnection, guild_id: int, author_id: int
) -> int:
    """Delete the author's own PENDING anecdotes (e.g. when they leave), return count deleted."""
    return await delete_pending_by_author(db, guild_id, author_id)
