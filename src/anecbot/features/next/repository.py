import aiosqlite


async def last_published_at(db: aiosqlite.Connection, guild_id: int) -> str | None:
    """Return the most recent published_at timestamp for a guild."""
    async with db.execute(
        "SELECT MAX(published_at) FROM anecdotes "
        "WHERE guild_id = ? AND state IN ('PUBLISHED', 'REVEALED')",
        (guild_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row and row[0] else None


async def earliest_pending_reveal(
    db: aiosqlite.Connection, guild_id: int
) -> str | None:
    """Return the earliest published_at of anecdotes awaiting reveal."""
    async with db.execute(
        "SELECT MIN(published_at) FROM anecdotes "
        "WHERE guild_id = ? AND state = 'PUBLISHED'",
        (guild_id,),
    ) as cursor:
        row = await cursor.fetchone()
    return row[0] if row and row[0] else None
