from pathlib import Path
from typing import cast

import aiosqlite
import discord
import pytest
import pytest_asyncio

from anecbot.features.publisher.service import (
    build_anecdote_embed,
    get_next_pending_anecdote,
    publish_next_anecdote,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2


class _FakeMessage:
    """Stand-in for a sent discord.Message — only .id is used by the service."""

    def __init__(self, message_id: int):
        self.id = message_id


class _FakeChannel:
    """Stand-in for a Messageable channel — records sends, returns a fake message."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed] = []

    async def send(self, embed: discord.Embed) -> _FakeMessage:
        """Record the embed and return a fake message with a fixed id."""
        self.sent_embeds.append(embed)
        return _FakeMessage(message_id=999)


class _FakeBot:
    """Stand-in for discord.Client — only get_channel is used by the service."""

    def __init__(self, channels: dict[int, _FakeChannel]):
        self._channels = channels

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def players(db):
    """Create a guild (with a configured channel) plus an author and a target player."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


@pytest.mark.asyncio
async def test_get_next_pending_anecdote_returns_oldest(db, players):
    """The oldest PENDING anecdote (by created_at) is returned first."""
    newer = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Newer",
        created_at="2026-01-02T10:00:00",
    )
    older = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Older",
        created_at="2026-01-01T10:00:00",
    )

    result = await get_next_pending_anecdote(db, GUILD_ID)
    assert result is not None
    assert result.id == older.id
    assert result.id != newer.id


@pytest.mark.asyncio
async def test_get_next_pending_anecdote_ignores_non_pending(db, players):
    """Only PENDING anecdotes are candidates."""
    published = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Old"
    )
    await Anecdote.update(db, published.id, state="PUBLISHED")

    assert await get_next_pending_anecdote(db, GUILD_ID) is None


@pytest.mark.asyncio
async def test_get_next_pending_anecdote_none_when_empty(db, players):
    """Returns None when there are no anecdotes at all."""
    assert await get_next_pending_anecdote(db, GUILD_ID) is None


def test_build_anecdote_embed_shows_content_only():
    """The embed shows the anecdote's content and no target/author info."""
    anecdote = Anecdote(
        id=1,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Un truc drôle",
    )

    embed = build_anecdote_embed(anecdote)

    assert embed.description == "Un truc drôle"
    assert str(AUTHOR_ID) not in (embed.title or "")
    assert str(TARGET_ID) not in (embed.title or "")


@pytest.mark.asyncio
async def test_publish_next_anecdote_transitions_to_running(db, players):
    """Publishing sends the embed, sets state to RUNNING, and stores the message id."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    result = await publish_next_anecdote(cast(discord.Client, bot), db, GUILD_ID)

    assert result is not None
    assert result.state == "RUNNING"
    assert result.anecdote_message_id == 999
    assert len(channel.sent_embeds) == 1
    assert channel.sent_embeds[0].description == "x"

    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "RUNNING"
    assert stored.anecdote_message_id == 999


@pytest.mark.asyncio
async def test_publish_next_anecdote_returns_none_when_queue_empty(db, players):
    """Returns None and sends nothing when there's no PENDING anecdote."""
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    result = await publish_next_anecdote(cast(discord.Client, bot), db, GUILD_ID)

    assert result is None
    assert channel.sent_embeds == []
