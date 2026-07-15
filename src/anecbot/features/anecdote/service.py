import aiosqlite

from anecbot.features.anecdote.repository import count_created_today
from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild


async def daily_limit_status(
    db: aiosqlite.Connection, guild_id: int, author_id: int
) -> tuple[bool, int]:
    """Return (reached, limit) for the author's daily submission limit."""
    guild = await Guild.get(db, guild_id)
    assert guild is not None
    if guild.daily_limit == 0:
        return False, 0
    count = await count_created_today(db, guild_id, author_id)
    return count >= guild.daily_limit, guild.daily_limit


async def create_anecdote(
    db: aiosqlite.Connection,
    guild_id: int,
    author_id: int,
    target_id: int,
    content: str,
) -> Anecdote:
    """Create a new anecdote in PENDING state."""
    return await Anecdote.create(
        db,
        guild_id=guild_id,
        author_id=author_id,
        target_id=target_id,
        content=content,
    )


async def get_pending_by_author(
    db: aiosqlite.Connection, guild_id: int, author_id: int
) -> list[Anecdote]:
    """Return the author's PENDING anecdotes in the guild, most recent first."""
    anecdotes = await Anecdote.list(
        db, guild_id=guild_id, author_id=author_id, state="PENDING"
    )
    return sorted(anecdotes, key=lambda a: (a.created_at, a.id), reverse=True)


async def get_owned_pending_anecdote(
    db: aiosqlite.Connection, anecdote_id: int, author_id: int
) -> Anecdote | None:
    """Return the anecdote if it exists, belongs to author_id, and is still PENDING."""
    anecdote = await Anecdote.get(db, anecdote_id)
    if (
        anecdote is None
        or anecdote.author_id != author_id
        or anecdote.state != "PENDING"
    ):
        return None
    return anecdote


async def update_content(
    db: aiosqlite.Connection, anecdote_id: int, content: str
) -> Anecdote:
    """Update a PENDING anecdote's content."""
    return await Anecdote.update(db, anecdote_id, content=content)


async def delete_anecdote(db: aiosqlite.Connection, anecdote_id: int) -> bool:
    """Delete an anecdote, return True if it existed."""
    return await Anecdote.delete(db, anecdote_id)
