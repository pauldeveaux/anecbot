import psycopg

from anecbot.models.enums import AnecdoteState


async def count_created_today(
    db: psycopg.AsyncConnection, guild_id: int, author_id: int
) -> int:
    """Count anecdotes created today (UTC) by the author in the guild."""
    cursor = await db.execute(
        "SELECT COUNT(*) FROM anecdotes "
        "WHERE guild_id = %s AND author_id = %s AND created_at::date = CURRENT_DATE",
        (guild_id, author_id),
    )
    row = await cursor.fetchone()
    assert row is not None
    return row[0]


async def has_any_for_user(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> bool:
    """Return whether the user has authored any anecdote in the guild.

    Targets are stored as frozen text labels in anecdote_choices, not as a live reference to a
    player row, so being a past target never blocks a player row from being deleted.
    """
    cursor = await db.execute(
        "SELECT 1 FROM anecdotes WHERE guild_id = %s AND author_id = %s LIMIT 1",
        (guild_id, user_id),
    )
    row = await cursor.fetchone()
    return row is not None


async def delete_pending_by_author(
    db: psycopg.AsyncConnection, guild_id: int, author_id: int
) -> int:
    """Delete the author's own PENDING anecdotes in the guild, return the count deleted."""
    cursor = await db.execute(
        "DELETE FROM anecdotes WHERE guild_id = %s AND author_id = %s AND state = %s",
        (guild_id, author_id, AnecdoteState.PENDING),
    )
    await db.commit()
    return cursor.rowcount
