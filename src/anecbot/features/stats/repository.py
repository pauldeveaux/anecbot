import psycopg

from anecbot.models.enums import AnecdoteState


async def count_correct_votes(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> int:
    """Count the user's votes that matched the anecdote's correct choice."""
    cursor = await db.execute(
        "SELECT COUNT(*) FROM votes v "
        "JOIN anecdote_choices c ON c.id = v.voted_for_id AND c.anecdote_id = v.anecdote_id "
        "WHERE v.guild_id = %s AND v.user_id = %s AND c.is_correct = 1",
        (guild_id, user_id),
    )
    row = await cursor.fetchone()
    assert row is not None
    return row[0]


async def average_quality_rating(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> float | None:
    """Average quality rating across the user's revealed anecdotes, or None if none rated."""
    cursor = await db.execute(
        "SELECT AVG(qv.rating) FROM anecdote_quality_votes qv "
        "JOIN anecdotes a ON a.id = qv.anecdote_id "
        "WHERE a.guild_id = %s AND a.author_id = %s AND a.state = %s",
        (guild_id, user_id, AnecdoteState.REVEALED),
    )
    row = await cursor.fetchone()
    assert row is not None
    average = row[0]
    return float(average) if average is not None else None
