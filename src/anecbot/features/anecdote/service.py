import aiosqlite

from anecbot.features.anecdote.repository import count_created_today
from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild


async def daily_limit_status(
    db: aiosqlite.Connection, guild_id: int, author_id: int
) -> tuple[bool, int]:
    """Return (reached, limit) for the author's daily submission limit."""
    guild = await Guild.get(db, guild_id)
    assert guild is not None
    if guild.daily_limit == 0:
        return False, 0
    count = await count_created_today(db, guild_id, author_id)
    return count >= guild.daily_limit, guild.daily_limit


async def create_anecdote(
    db: aiosqlite.Connection,
    guild_id: int,
    author_id: int,
    target_id: int,
    content: str,
) -> Anecdote:
    """Create a new anecdote in PENDING state."""
    return await Anecdote.create(
        db,
        guild_id=guild_id,
        author_id=author_id,
        target_id=target_id,
        content=content,
    )
