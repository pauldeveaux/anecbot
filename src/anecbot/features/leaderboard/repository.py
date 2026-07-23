import psycopg

from anecbot.models.enums import AnecdoteState


async def count_votes_by_user(
    db: psycopg.AsyncConnection, guild_id: int
) -> list[tuple[int, int]]:
    """Return (user_id, votes_cast) pairs for the guild, ranked descending."""
    cursor = await db.execute(
        "SELECT user_id, COUNT(*) FROM votes WHERE guild_id = %s "
        "GROUP BY user_id ORDER BY 2 DESC",
        (guild_id,),
    )
    rows = await cursor.fetchall()
    return [(row[0], row[1]) for row in rows]


async def count_correct_votes_by_user(
    db: psycopg.AsyncConnection, guild_id: int
) -> dict[int, int]:
    """Return user_id -> correct-vote count for the guild."""
    cursor = await db.execute(
        "SELECT v.user_id, COUNT(*) FROM votes v "
        "JOIN anecdote_choices c ON c.id = v.voted_for_id AND c.anecdote_id = v.anecdote_id "
        "WHERE v.guild_id = %s AND c.is_correct = 1 "
        "GROUP BY v.user_id",
        (guild_id,),
    )
    rows = await cursor.fetchall()
    return {row[0]: row[1] for row in rows}


async def count_revealed_by_author(
    db: psycopg.AsyncConnection, guild_id: int
) -> list[tuple[int, int]]:
    """Return (author_id, revealed_count) pairs for the guild, ranked descending.

    Only counts REVEALED anecdotes (never PUBLISHED/REVEALING) so a player's rank can't be
    cross-referenced against a currently-published anecdote to guess who wrote it.
    """
    cursor = await db.execute(
        "SELECT author_id, COUNT(*) FROM anecdotes WHERE guild_id = %s AND state = %s "
        "GROUP BY author_id ORDER BY 2 DESC",
        (guild_id, AnecdoteState.REVEALED),
    )
    rows = await cursor.fetchall()
    return [(row[0], row[1]) for row in rows]


async def delete_all_entries(db: psycopg.AsyncConnection, guild_id: int) -> None:
    """Delete every leaderboard entry for the guild."""
    await db.execute("DELETE FROM leaderboard WHERE guild_id = %s", (guild_id,))
    await db.commit()


async def claim_leaderboard_reset(db: psycopg.AsyncConnection, guild_id: int) -> bool:
    """Atomically claim the leaderboard reset cycle; return False if already in progress."""
    cursor = await db.execute(
        "UPDATE guilds SET leaderboard_reset_in_progress = 1 "
        "WHERE guild_id = %s AND leaderboard_reset_in_progress = 0",
        (guild_id,),
    )
    await db.commit()
    return cursor.rowcount > 0


async def mark_leaderboard_published(
    db: psycopg.AsyncConnection, guild_id: int
) -> None:
    """Record that the pre-reset standings message was sent."""
    await db.execute(
        "UPDATE guilds SET leaderboard_reset_published = 1 WHERE guild_id = %s",
        (guild_id,),
    )
    await db.commit()
