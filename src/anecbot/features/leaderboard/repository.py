import aiosqlite


async def delete_all_entries(db: aiosqlite.Connection, guild_id: int) -> None:
    """Delete every leaderboard entry for the guild."""
    await db.execute("DELETE FROM leaderboard WHERE guild_id = ?", (guild_id,))
    await db.commit()
