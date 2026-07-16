import aiosqlite


async def count_total_published(db: aiosqlite.Connection, guild_id: int) -> int:
    """Count every PUBLISHED/REVEALED anecdote ever in the guild."""
    async with db.execute(
        "SELECT COUNT(*) FROM anecdotes "
        "WHERE guild_id = ? AND state IN ('PUBLISHED', 'REVEALED')",
        (guild_id,),
    ) as cursor:
        row = await cursor.fetchone()
    assert row is not None
    return row[0]


async def get_author_publish_distances(
    db: aiosqlite.Connection, guild_id: int, author_id: int
) -> list[int]:
    """For each of the author's past published anecdotes, count how many others were published since."""
    async with db.execute(
        "SELECT ("
        "  SELECT COUNT(*) FROM anecdotes b"
        "  WHERE b.guild_id = a.guild_id AND b.state IN ('PUBLISHED', 'REVEALED')"
        "  AND b.published_at > a.published_at"
        ") AS distance "
        "FROM anecdotes a "
        "WHERE a.guild_id = ? AND a.author_id = ? AND a.state IN ('PUBLISHED', 'REVEALED')",
        (guild_id, author_id),
    ) as cursor:
        rows = await cursor.fetchall()
    return [row[0] for row in rows]
