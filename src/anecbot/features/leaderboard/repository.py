import psycopg


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
