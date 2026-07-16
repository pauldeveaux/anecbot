from datetime import datetime
from pathlib import Path
from typing import cast

import aiosqlite
import discord
import pytest
import pytest_asyncio

from anecbot.features.publisher.service import (
    build_anecdote_embed,
    get_next_pending_anecdote,
    publish_and_open_voting,
    publish_next_anecdote,
    recover_stuck_publications,
    refresh_published_reveal_dates,
    send_empty_queue_warning,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.utils.text import with_blank_lines

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2


class _FakeMessage:
    """Stand-in for a sent discord.Message — .id is read, .edit() calls are recorded."""

    def __init__(self, message_id: int):
        self.id = message_id
        self.edit_kwargs: dict[str, object] | None = None

    async def edit(self, **kwargs: object) -> None:
        """Record exactly which kwargs edit() was called with."""
        self.edit_kwargs = kwargs


class _FakeChannel:
    """Stand-in for a Messageable channel — records sends, returns fake messages."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed | None] = []
        self.sent_contents: list[str | None] = []
        self._messages: dict[int, _FakeMessage] = {}

    async def send(
        self, content: str | None = None, *, embed: discord.Embed | None = None
    ) -> _FakeMessage:
        """Record the send and return a fake message with a fixed id."""
        self.sent_embeds.append(embed)
        self.sent_contents.append(content)
        message = _FakeMessage(message_id=999)
        self._messages[message.id] = message
        return message

    async def fetch_message(self, message_id: int) -> _FakeMessage:
        """Return the previously sent fake message matching the id."""
        return self._messages[message_id]


class _FakeGuild:
    """Stand-in for discord.Guild — only get_member is used (via display_name)."""

    def __init__(self, guild_id: int):
        self.id = guild_id

    def get_member(self, user_id: int) -> None:
        """No cached members in tests — display_name falls back to alias/user id."""
        return None


class _FakeBot:
    """Stand-in for discord.Client — get_channel/get_guild are used by the service."""

    def __init__(
        self, channels: dict[int, _FakeChannel], guild: _FakeGuild | None = None
    ):
        self._channels = channels
        self._guild = guild

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """Return the configured fake guild, or None."""
        return self._guild


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
    """The embed shows the anecdote's content and no target/author info, no reveal date."""
    anecdote = Anecdote(
        id=1,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Un truc drôle",
    )

    embed = build_anecdote_embed(anecdote)

    content_field = embed.fields[0]
    assert content_field.value == with_blank_lines("Un truc drôle")
    assert str(AUTHOR_ID) not in (embed.title or "")
    assert str(TARGET_ID) not in (embed.title or "")
    assert all(f.name != "🔍 Révélation prévue" for f in embed.fields)


def test_build_anecdote_embed_shows_reveal_date_when_given():
    """When a reveal_at datetime is passed, it's shown as a dedicated field."""
    anecdote = Anecdote(
        id=1, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    reveal_at = datetime(2026, 7, 15, 13, 30)

    embed = build_anecdote_embed(anecdote, reveal_at)

    reveal_field = next(f for f in embed.fields if f.name == "🔍 Révélation prévue")
    assert reveal_field.value is not None


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
    sent_embed = channel.sent_embeds[0]
    assert sent_embed is not None
    content_field = sent_embed.fields[0]
    assert content_field.value == with_blank_lines("x")

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


@pytest.mark.asyncio
async def test_send_empty_queue_warning_sends_once(db, players):
    """The warning is sent and the flag is set when not already warned."""
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    await send_empty_queue_warning(cast(discord.Client, bot), db, guild)

    assert len(channel.sent_contents) == 1
    updated = await Guild.get(db, GUILD_ID)
    assert updated is not None
    assert updated.queue_empty_warned == 1


@pytest.mark.asyncio
async def test_send_empty_queue_warning_skips_when_already_warned(db, players):
    """No duplicate warning is sent once the flag is already set."""
    await Guild.upsert(db, GUILD_ID, queue_empty_warned=1)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    await send_empty_queue_warning(cast(discord.Client, bot), db, guild)

    assert channel.sent_contents == []


@pytest.mark.asyncio
async def test_publish_and_open_voting_reaches_published(db, players):
    """Publishing attaches the MCQ, shows the reveal date, and sets published_at."""
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    result = await publish_and_open_voting(cast(discord.Client, bot), db, GUILD_ID)

    assert result is not None
    assert result.state == "PUBLISHED"
    assert result.published_at is not None

    sent_message = channel._messages[999]
    assert sent_message.edit_kwargs is not None
    assert isinstance(sent_message.edit_kwargs["view"], discord.ui.View)
    published_embed = sent_message.edit_kwargs["embed"]
    assert isinstance(published_embed, discord.Embed)
    assert any(f.name == "🔍 Révélation prévue" for f in published_embed.fields)


@pytest.mark.asyncio
async def test_publish_and_open_voting_warns_once_when_empty(db, players):
    """An empty queue triggers the warning once, not on a second call."""
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    first = await publish_and_open_voting(cast(discord.Client, bot), db, GUILD_ID)
    second = await publish_and_open_voting(cast(discord.Client, bot), db, GUILD_ID)

    assert first is None
    assert second is None
    assert len(channel.sent_contents) == 1


@pytest.mark.asyncio
async def test_refresh_published_reveal_dates_updates_message(db, players):
    """Every PUBLISHED anecdote's message is re-edited with a fresh reveal date."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    await Anecdote.update(
        db,
        anecdote.id,
        state="PUBLISHED",
        published_at="2026-07-13T15:00:00",
        anecdote_message_id=999,
    )
    channel = _FakeChannel()
    channel._messages[999] = _FakeMessage(999)
    bot = _FakeBot({CHANNEL_ID: channel})

    await refresh_published_reveal_dates(cast(discord.Client, bot), db, GUILD_ID)

    message = channel._messages[999]
    assert message.edit_kwargs is not None
    updated_embed = message.edit_kwargs["embed"]
    assert isinstance(updated_embed, discord.Embed)
    assert any(f.name == "🔍 Révélation prévue" for f in updated_embed.fields)
    assert "view" not in message.edit_kwargs


@pytest.mark.asyncio
async def test_refresh_published_reveal_dates_ignores_non_published(db, players):
    """PENDING/RUNNING/REVEALED anecdotes' messages are left untouched."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="RUNNING", anecdote_message_id=999)
    channel = _FakeChannel()
    channel._messages[999] = _FakeMessage(999)
    bot = _FakeBot({CHANNEL_ID: channel})

    await refresh_published_reveal_dates(cast(discord.Client, bot), db, GUILD_ID)

    assert channel._messages[999].edit_kwargs is None


@pytest.mark.asyncio
async def test_refresh_published_reveal_dates_no_channel_configured(db):
    """No-op when the guild has no channel configured (nothing to crash on)."""
    await Guild.upsert(db, GUILD_ID)
    bot = _FakeBot({})

    await refresh_published_reveal_dates(cast(discord.Client, bot), db, GUILD_ID)


# --- recover_stuck_publications ---


@pytest.mark.asyncio
async def test_recover_stuck_publications_finishes_when_message_was_sent(db, players):
    """A RUNNING anecdote with a known message id resumes to PUBLISHED with the MCQ view."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="RUNNING", anecdote_message_id=999)
    channel = _FakeChannel()
    channel._messages[999] = _FakeMessage(999)
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 1
    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "PUBLISHED"
    assert stored.published_at is not None
    edit_kwargs = channel._messages[999].edit_kwargs
    assert edit_kwargs is not None
    assert isinstance(edit_kwargs["view"], discord.ui.View)


@pytest.mark.asyncio
async def test_recover_stuck_publications_reverts_when_message_was_never_sent(
    db, players
):
    """A RUNNING anecdote with no known message id reverts to PENDING for a clean retry."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="RUNNING")
    bot = _FakeBot({}, guild=_FakeGuild(GUILD_ID))

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 1
    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "PENDING"


@pytest.mark.asyncio
async def test_recover_stuck_publications_ignores_other_states(db, players):
    """PENDING/PUBLISHED/REVEALED anecdotes are left untouched."""
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    bot = _FakeBot({}, guild=_FakeGuild(GUILD_ID))

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 0
    stored = await Anecdote.get(db, pending.id)
    assert stored is not None
    assert stored.state == "PENDING"


@pytest.mark.asyncio
async def test_recover_stuck_publications_no_channel_configured(db):
    """No-op when the guild has no channel configured."""
    await Guild.upsert(db, GUILD_ID)
    bot = _FakeBot({})

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 0
