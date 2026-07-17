import aiosqlite


async def claim_points_award(db: aiosqlite.Connection, anecdote_id: int) -> bool:
    """Atomically claim the points award for the anecdote; return False if already claimed."""
    cursor = await db.execute(
        "UPDATE anecdotes SET points_awarded = 1 WHERE id = ? AND points_awarded = 0",
        (anecdote_id,),
    )
    await db.commit()
    return cursor.rowcount > 0
