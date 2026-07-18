import psycopg


async def delete_all_guild_data(db: psycopg.AsyncConnection, guild_id: int) -> None:
    """Delete every vote, anecdote, leaderboard entry, and player for the guild."""
    await db.execute("DELETE FROM votes WHERE guild_id = %s", (guild_id,))
    await db.execute("DELETE FROM anecdotes WHERE guild_id = %s", (guild_id,))
    await db.execute("DELETE FROM leaderboard WHERE guild_id = %s", (guild_id,))
    await db.execute("DELETE FROM players WHERE guild_id = %s", (guild_id,))
    await db.commit()
