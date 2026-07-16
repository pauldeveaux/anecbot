from datetime import datetime
from pathlib import Path
from typing import cast
from zoneinfo import ZoneInfo

import aiosqlite
import discord
import pytest
import pytest_asyncio

from anecbot.features.scheduler.service import (
    check_publication_for_guild,
    check_publications,
    is_publication_due,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
OTHER_GUILD_ID = 200
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2

WEEKEND = {5, 6}  # Saturday, Sunday
PARIS = ZoneInfo("Europe/Paris")


class _FakeMessage:
    """Stand-in for a sent discord.Message — .id is read, .edit() calls are recorded."""

    def __init__(self, message_id: int):
        self.id = message_id

    async def edit(self, **kwargs: object) -> None:
        """No-op edit for scheduler tests — only publish_and_open_voting's side effects matter."""


class _FakeChannel:
    """Stand-in for a Messageable channel — records sends, returns fake messages."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed | None] = []
        self._messages: dict[int, _FakeMessage] = {}

    async def send(self, *, embed: discord.Embed | None = None) -> _FakeMessage:
        """Record the send and return a fake message with a fixed id."""
        self.sent_embeds.append(embed)
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

    def __init__(self, channels: dict[int, _FakeChannel]):
        self._channels = channels

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """Return a fake discord.Guild for any id."""
        return _FakeGuild(guild_id)


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
    """Create a guild (started, with a channel) plus an author and a target player."""
    await Guild.upsert(
        db, GUILD_ID, channel_id=CHANNEL_ID, started=1, publish_time="15:00"
    )
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


# --- is_publication_due — never published before ---


def test_is_publication_due_first_time_active_day_time_reached():
    """Never published, active day, current time past publish_time → due."""
    now = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    assert is_publication_due(None, 1, "15:00", set(), now) is True


def test_is_publication_due_first_time_time_not_reached():
    """Never published, active day, current time before publish_time → not due."""
    now = datetime(2026, 7, 13, 10, 0)  # Monday 10:00
    assert is_publication_due(None, 1, "15:00", set(), now) is False


def test_is_publication_due_first_time_day_off():
    """Never published, today is a day off → not due, regardless of time."""
    now = datetime(2026, 7, 18, 16, 0)  # Saturday 16:00
    assert is_publication_due(None, 1, "15:00", WEEKEND, now) is False


# --- is_publication_due — subsequent ---


def test_is_publication_due_subsequent_reached():
    """Interval elapsed and target time reached → due."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday
    now = datetime(2026, 7, 14, 15, 0)  # Tuesday, interval=1 → due at 15:00
    assert is_publication_due(last, 1, "15:00", set(), now) is True


def test_is_publication_due_subsequent_not_yet():
    """Interval elapsed but target time not reached yet → not due."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday
    now = datetime(2026, 7, 14, 10, 0)  # Tuesday 10:00, before 15:00
    assert is_publication_due(last, 1, "15:00", set(), now) is False


def test_is_publication_due_subsequent_interval_not_elapsed():
    """Interval not elapsed yet → not due even if time-of-day matches."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday
    now = datetime(2026, 7, 13, 16, 0)  # Same day, interval=2 not elapsed
    assert is_publication_due(last, 2, "15:00", set(), now) is False


def test_is_publication_due_catch_up_after_long_offline():
    """A long-overdue publication is still reported as due (idempotent catch-up)."""
    last = datetime(2026, 7, 1, 15, 0)  # Two weeks ago
    now = datetime(2026, 7, 14, 10, 0)
    assert is_publication_due(last, 1, "15:00", set(), now) is True


def test_is_publication_due_respects_timezone_across_midnight():
    """A last_published moment landing on a different local calendar day changes the due date."""
    last = datetime(2026, 7, 13, 23, 0)  # 23:00 UTC Monday = 01:00 CEST Tuesday
    # local last_published date is Tuesday 07-14 -> next active day (+1) = Wednesday 07-15
    # 15:00 Paris (CEST) = 13:00 UTC
    just_before = datetime(2026, 7, 15, 12, 55)
    just_after = datetime(2026, 7, 15, 13, 5)

    assert is_publication_due(last, 1, "15:00", set(), just_before, PARIS) is False
    assert is_publication_due(last, 1, "15:00", set(), just_after, PARIS) is True
    # a plain UTC interpretation would already have been due a full day earlier
    assert is_publication_due(last, 1, "15:00", set(), just_before) is True


# --- check_publication_for_guild ---


@pytest.mark.asyncio
async def test_check_publication_for_guild_skips_when_not_started(db):
    """A guild with started=0 is never checked, regardless of timing."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID, started=0)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publication_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is False
    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_check_publication_for_guild_skips_when_no_channel(db):
    """A guild with no channel configured is never checked."""
    await Guild.upsert(db, GUILD_ID, started=1)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    triggered = await check_publication_for_guild(
        cast(discord.Client, _FakeBot({})), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is False


@pytest.mark.asyncio
async def test_check_publication_for_guild_skips_when_not_due(db, players):
    """Nothing is published if the publication isn't due yet."""
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publication_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 10, 0)
    )

    assert triggered is False
    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_check_publication_for_guild_triggers_when_due(db, players):
    """A due, started guild with a pending anecdote gets published."""
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publication_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is True
    assert len(channel.sent_embeds) == 1


# --- check_publications ---


@pytest.mark.asyncio
async def test_check_publications_only_checks_started_guilds(db, players):
    """A stopped guild is skipped even if otherwise due."""
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    await Guild.upsert(db, OTHER_GUILD_ID, channel_id=CHANNEL_ID, started=0)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publications(
        cast(discord.Client, bot), db, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered == 1
    assert len(channel.sent_embeds) == 1
