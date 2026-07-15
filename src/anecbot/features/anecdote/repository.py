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


async def has_any_for_user(
    db: aiosqlite.Connection, guild_id: int, user_id: int
) -> bool:
    """Return whether the user has any anecdotes as author or target in the guild."""
    async with db.execute(
        "SELECT 1 FROM anecdotes WHERE guild_id = ? AND (author_id = ? OR target_id = ?) "
        "LIMIT 1",
        (guild_id, user_id, user_id),
    ) as cursor:
        row = await cursor.fetchone()
    return row is not None


async def delete_pending_by_author(
    db: aiosqlite.Connection, guild_id: int, author_id: int
) -> int:
    """Delete the author's own PENDING anecdotes in the guild, return the count deleted."""
    cursor = await db.execute(
        "DELETE FROM anecdotes WHERE guild_id = ? AND author_id = ? AND state = 'PENDING'",
        (guild_id, author_id),
    )
    await db.commit()
    return cursor.rowcount
