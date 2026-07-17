import aiosqlite

from anecbot.models.enums import AnecdoteState


async def last_published_at(db: aiosqlite.Connection, guild_id: int) -> str | None:
    """Return the most recent published_at timestamp for a guild."""
    async with db.execute(
        "SELECT MAX(published_at) FROM anecdotes "
        "WHERE guild_id = ? AND state IN (?, ?)",
        (guild_id, AnecdoteState.PUBLISHED, AnecdoteState.REVEALED),
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row and row[0] else None


async def earliest_pending_reveal(
    db: aiosqlite.Connection, guild_id: int
) -> str | None:
    """Return the earliest published_at of anecdotes awaiting reveal."""
    async with db.execute(
        "SELECT MIN(published_at) FROM anecdotes WHERE guild_id = ? AND state = ?",
        (guild_id, AnecdoteState.PUBLISHED),
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row and row[0] else None
