import logging
from datetime import datetime, timezone
from typing import cast

import aiosqlite
import discord

from anecbot.features.lifecycle.repository import delete_all_guild_data
from anecbot.models.guild import Guild

logger = logging.getLogger(__name__)


async def wipe_guild_data(db: aiosqlite.Connection, guild_id: int) -> None:
    """Delete all game data for the guild and stop the game."""
    await delete_all_guild_data(db, guild_id)
    await Guild.upsert(db, guild_id, started=0, started_at=None)
    logger.warning("All data wiped for guild %s", guild_id)


async def start_game(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> None:
    """Mark the game started and announce it publicly, first start vs. resume wording."""
    guild = await Guild.get(db, guild_id)
    assert guild is not None
    assert guild.channel_id is not None

    is_first_start = guild.started_at is None
    kwargs: dict[str, object] = {"started": 1}
    if is_first_start:
        kwargs["started_at"] = datetime.now(timezone.utc).isoformat()
    await Guild.upsert(db, guild_id, **kwargs)
    logger.info("Game started for guild %s", guild_id)

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    if channel is None:
        return
    if is_first_start:
        await channel.send(
            "🎉 Le jeu commence ! Les anecdotes seront publiées régulièrement dans ce channel. "
            "Utilisez `/rules` pour voir comment participer."
        )
    else:
        await channel.send(
            "▶️ Le jeu reprend ! Les publications recommencent selon la configuration."
        )


async def stop_game(
    bot: discord.Client, db: aiosqlite.Connection, guild_id: int
) -> None:
    """Mark the game stopped and announce it publicly."""
    guild = await Guild.get(db, guild_id)
    assert guild is not None
    assert guild.channel_id is not None

    await Guild.upsert(db, guild_id, started=0)
    logger.info("Game stopped for guild %s", guild_id)

    channel = cast("discord.abc.Messageable | None", bot.get_channel(guild.channel_id))
    if channel is None:
        return
    await channel.send(
        "⏸️ Le jeu est en pause. Plus aucune publication jusqu'à la reprise."
    )
