import logging

import aiosqlite

from anecbot.features.lifecycle.repository import delete_all_guild_data
from anecbot.models.guild import Guild

logger = logging.getLogger(__name__)


async def wipe_guild_data(db: aiosqlite.Connection, guild_id: int) -> None:
    """Delete all game data for the guild and stop the game."""
    await delete_all_guild_data(db, guild_id)
    await Guild.upsert(db, guild_id, started=0, started_at=None)
    logger.warning("All data wiped for guild %s", guild_id)
