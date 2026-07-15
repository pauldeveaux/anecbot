import aiosqlite


async def count_created_today(
    db: aiosqlite.Connection, guild_id: int, author_id: int
) -> int:
    """Count anecdotes created today (UTC) by the author in the guild."""
    async with db.execute(
        "SELECT COUNT(*) FROM anecdotes "
        "WHERE guild_id = ? AND author_id = ? AND date(created_at) = date('now')",
        (guild_id, author_id),
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None
    return row[0]
