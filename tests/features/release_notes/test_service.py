from pathlib import Path
from typing import cast

import discord
import pytest

from anecbot.features.release_notes.service import (
    announce_release_if_new,
    read_release_notes,
)
from anecbot.models.guild import Guild
from anecbot.models.release_announcement import ReleaseAnnouncement

GUILD_ID = 100
CHANNEL_ID = 555
OTHER_GUILD_ID = 200
OTHER_CHANNEL_ID = 666


class _FakeChannel:
    """Stand-in for a Messageable channel — records embeds sent to it."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed] = []

    async def send(self, *, embed: discord.Embed) -> None:
        """Record the embed sent."""
        self.sent_embeds.append(embed)


class _FakeBot:
    """Stand-in for discord.Client — only get_channel is used by the service."""

    def __init__(self, channels: dict[int, _FakeChannel]):
        self._channels = channels

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)


def _bot(fake: _FakeBot) -> discord.Client:
    """Cast a _FakeBot to discord.Client, matching what the service only actually uses."""
    return cast(discord.Client, fake)


def _release_notes_file(tmp_path: Path, content: str) -> Path:
    """Write content to a RELEASE_NOTES.md under tmp_path and return its path."""
    path = tmp_path / "RELEASE_NOTES.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_read_release_notes_missing_file_returns_none(tmp_path):
    """A path that doesn't exist yields None."""
    assert read_release_notes(tmp_path / "missing.md") is None


def test_read_release_notes_blank_content_returns_none(tmp_path):
    """Whitespace-only content is treated as no message."""
    path = _release_notes_file(tmp_path, "   \n\n  ")
    assert read_release_notes(path) is None


def test_read_release_notes_returns_stripped_content(tmp_path):
    """Leading/trailing whitespace is stripped from the file's content."""
    path = _release_notes_file(tmp_path, "  Nouvelle version !  \n")
    assert read_release_notes(path) == "Nouvelle version !"


@pytest.mark.asyncio
async def test_announce_release_if_new_returns_zero_when_no_notes(db, tmp_path):
    """No file, no announcement, and nothing is recorded."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    bot = _FakeBot({CHANNEL_ID: _FakeChannel()})

    sent = await announce_release_if_new(_bot(bot), db, tmp_path / "missing.md")

    assert sent == 0
    assert await ReleaseAnnouncement.get(db, 1) is None


@pytest.mark.asyncio
async def test_announce_release_if_new_sends_to_every_configured_guild(db, tmp_path):
    """New content is sent to every guild with a channel configured, and the hash is stored."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    await Guild.upsert(db, OTHER_GUILD_ID, channel_id=OTHER_CHANNEL_ID)
    channel_a = _FakeChannel()
    channel_b = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel_a, OTHER_CHANNEL_ID: channel_b})
    path = _release_notes_file(tmp_path, "v2.0 : nouvelles fonctionnalités !")

    sent = await announce_release_if_new(_bot(bot), db, path)

    assert sent == 2
    description_a = channel_a.sent_embeds[0].description
    description_b = channel_b.sent_embeds[0].description
    assert description_a is not None and "v2.0" in description_a
    assert description_b is not None and "v2.0" in description_b
    record = await ReleaseAnnouncement.get(db, 1)
    assert record is not None
    assert record.content_hash is not None
    assert record.announced_at is not None


@pytest.mark.asyncio
async def test_announce_release_if_new_skips_guild_without_channel(db, tmp_path):
    """A guild with no channel_id configured is never sent to."""
    await Guild.upsert(db, GUILD_ID, channel_id=None)
    bot = _FakeBot({})
    path = _release_notes_file(tmp_path, "v2.0")

    sent = await announce_release_if_new(_bot(bot), db, path)

    assert sent == 0


@pytest.mark.asyncio
async def test_announce_release_if_new_does_not_repeat_unchanged_content(db, tmp_path):
    """Calling again with the same content sends nothing the second time."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    path = _release_notes_file(tmp_path, "v2.0")

    first = await announce_release_if_new(_bot(bot), db, path)
    second = await announce_release_if_new(_bot(bot), db, path)

    assert first == 1
    assert second == 0
    assert len(channel.sent_embeds) == 1


@pytest.mark.asyncio
async def test_announce_release_if_new_skips_guild_that_joined_after_announcement(
    db, tmp_path
):
    """A guild whose channel is configured only after the hash was recorded gets nothing
    once a later call finds the content unchanged — no backlog for late joiners."""
    path = _release_notes_file(tmp_path, "v2.0")
    channel_early = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel_early})
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)

    first = await announce_release_if_new(_bot(bot), db, path)
    assert first == 1

    # A new guild joins and configures its channel only now, after v2.0 was already announced.
    channel_late = _FakeChannel()
    bot._channels[OTHER_CHANNEL_ID] = channel_late
    await Guild.upsert(db, OTHER_GUILD_ID, channel_id=OTHER_CHANNEL_ID)

    second = await announce_release_if_new(_bot(bot), db, path)

    assert second == 0
    assert channel_late.sent_embeds == []
