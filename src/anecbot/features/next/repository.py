import psycopg

from anecbot.models.enums import AnecdoteState


async def last_published_at(db: psycopg.AsyncConnection, guild_id: int) -> str | None:
    """Return the most recent published_at timestamp for a guild."""
    cursor = await db.execute(
        "SELECT MAX(published_at) FROM anecdotes "
        "WHERE guild_id = %s AND state IN (%s, %s)",
        (guild_id, AnecdoteState.PUBLISHED, AnecdoteState.REVEALED),
    )
    row = await cursor.fetchone()
    return row[0] if row and row[0] else None


async def earliest_pending_reveal(
    db: psycopg.AsyncConnection, guild_id: int
) -> str | None:
    """Return the earliest published_at of anecdotes awaiting reveal."""
    cursor = await db.execute(
        "SELECT MIN(published_at) FROM anecdotes WHERE guild_id = %s AND state = %s",
        (guild_id, AnecdoteState.PUBLISHED),
    )
    row = await cursor.fetchone()
    return row[0] if row and row[0] else None
