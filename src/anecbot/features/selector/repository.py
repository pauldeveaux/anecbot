import aiosqlite

from anecbot.models.enums import AnecdoteState

_PUBLISHED_OR_REVEALED = (AnecdoteState.PUBLISHED, AnecdoteState.REVEALED)


async def count_total_published(db: aiosqlite.Connection, guild_id: int) -> int:
    """Count every PUBLISHED/REVEALED anecdote ever in the guild."""
    async with db.execute(
        "SELECT COUNT(*) FROM anecdotes WHERE guild_id = ? AND state IN (?, ?)",
        (guild_id, *_PUBLISHED_OR_REVEALED),
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
        "  WHERE b.guild_id = a.guild_id AND b.state IN (?, ?)"
        "  AND b.published_at > a.published_at"
        ") AS distance "
        "FROM anecdotes a "
        "WHERE a.guild_id = ? AND a.author_id = ? AND a.state IN (?, ?)",
        (*_PUBLISHED_OR_REVEALED, guild_id, author_id, *_PUBLISHED_OR_REVEALED),
    ) as cursor:
        rows = await cursor.fetchall()
    return [row[0] for row in rows]


async def get_author_publish_distances_bulk(
    db: aiosqlite.Connection, guild_id: int, author_ids: list[int]
) -> dict[int, list[int]]:
    """Same as get_author_publish_distances, batched for several authors in one query."""
    if not author_ids:
        return {}
    placeholders = ", ".join("?" for _ in author_ids)
    async with db.execute(
        "SELECT a.author_id, ("
        "  SELECT COUNT(*) FROM anecdotes b"
        "  WHERE b.guild_id = a.guild_id AND b.state IN (?, ?)"
        "  AND b.published_at > a.published_at"
        ") AS distance "
        "FROM anecdotes a "
        f"WHERE a.guild_id = ? AND a.author_id IN ({placeholders}) AND a.state IN (?, ?)",
        (*_PUBLISHED_OR_REVEALED, guild_id, *author_ids, *_PUBLISHED_OR_REVEALED),
    ) as cursor:
        rows = await cursor.fetchall()
    result: dict[int, list[int]] = {author_id: [] for author_id in author_ids}
    for author_id, distance in rows:
        result[author_id].append(distance)
    return result
