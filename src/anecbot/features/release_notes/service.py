import hashlib
import logging
from pathlib import Path
from typing import cast

import discord
import psycopg

from anecbot.models.guild import Guild
from anecbot.models.release_announcement import ReleaseAnnouncement
from anecbot.utils.time import utcnow

logger = logging.getLogger(__name__)

EMBED_DESCRIPTION_LIMIT = 4096


def read_release_notes(path: Path) -> str | None:
    """Return the stripped release notes file content, or None if missing or blank."""
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8").strip()
    return content or None


async def announce_release_if_new(
    bot: discord.Client, db: psycopg.AsyncConnection, release_notes_path: Path
) -> int:
    """Announce release_notes_path's content to every guild's channel, once per distinct message.

    A guild only receives an announcement if its channel is already configured at the moment
    the content hash changes — a guild that joins (or configures its channel) after that point
    never receives it, since an unchanged hash skips the whole send loop on later restarts.
    """
    notes = read_release_notes(release_notes_path)
    if notes is None:
        return 0

    content_hash = hashlib.sha256(notes.encode("utf-8")).hexdigest()
    record = await ReleaseAnnouncement.get(db, 1)
    if record is not None and record.content_hash == content_hash:
        return 0

    embed = discord.Embed(
        description=notes[:EMBED_DESCRIPTION_LIMIT],
        color=discord.Color.green(),
    )

    guilds = [g for g in await Guild.list(db) if g.channel_id is not None]
    sent = 0
    for guild in guilds:
        assert guild.channel_id is not None
        channel = cast(
            "discord.abc.Messageable | None", bot.get_channel(guild.channel_id)
        )
        if channel is None:
            continue
        try:
            await channel.send(embed=embed)
            sent += 1
        except discord.HTTPException:
            logger.exception(
                "Failed to send release announcement to guild %s", guild.guild_id
            )

    await ReleaseAnnouncement.upsert(
        db, 1, content_hash=content_hash, announced_at=utcnow().isoformat()
    )
    logger.info("Release announcement sent to %d/%d guild(s)", sent, len(guilds))
    return sent
