from datetime import datetime
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.models.database import run_migrations
from anecbot.models.enums import LeaderboardResetMode, RevealMode
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.features.next.service import get_next_events

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_game_not_started(db):
    """No events when game is stopped."""
    await Guild.upsert(db, GUILD_ID, channel_id=1, started=0)
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication is None
    assert events.next_reveal is None
    assert events.leaderboard_reset_hidden is True


@pytest.mark.asyncio
async def test_game_no_channel(db):
    """No events when no channel configured."""
    await Guild.upsert(db, GUILD_ID, started=1)
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication is None


@pytest.mark.asyncio
async def test_no_guild(db):
    """No events for unknown guild."""
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, 999, now)
    assert events.next_publication is None


@pytest.mark.asyncio
async def test_first_publication(db):
    """Next publication when no anecdotes published yet."""
    await Guild.upsert(
        db, GUILD_ID, channel_id=1, started=1, publish_time="15:00", interval_days=1
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication == datetime(2026, 7, 15, 15, 0)


@pytest.mark.asyncio
async def test_publication_after_previous(db):
    """Next publication computed from last published anecdote."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=2,
        days_off="",
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(
        db, GUILD_ID, 1, 2, "2026-07-14T15:00:00", "PUBLISHED"
    )

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication == datetime(2026, 7, 16, 15, 0)


@pytest.mark.asyncio
async def test_reveal_after_publish_mode(db):
    """Next reveal for after-publish mode with a PUBLISHED anecdote."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        reveal_mode=RevealMode.AFTER_PUBLISH,
        reveal_interval_days=1,
        reveal_time="13:30",
        days_off="",
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(
        db, GUILD_ID, 1, 2, "2026-07-14T15:00:00", "PUBLISHED"
    )

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_reveal == datetime(2026, 7, 15, 13, 30)
    assert events.reveal_placeholder is False


@pytest.mark.asyncio
async def test_reveal_no_published_anecdotes(db):
    """No reveal when no anecdotes are awaiting reveal."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        reveal_mode=RevealMode.AFTER_PUBLISH,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_reveal is None
    assert events.reveal_placeholder is False


@pytest.mark.asyncio
async def test_reveal_interval_mode_placeholder(db):
    """Interval reveal mode shows placeholder."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        reveal_mode=RevealMode.INTERVAL,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_reveal is None
    assert events.reveal_placeholder is True


@pytest.mark.asyncio
async def test_leaderboard_reset_never_hidden(db):
    """Leaderboard reset hidden when mode is NEVER."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        leaderboard_reset_mode=LeaderboardResetMode.NEVER,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.leaderboard_reset_hidden is True
    assert events.leaderboard_reset_placeholder is False


@pytest.mark.asyncio
async def test_leaderboard_reset_non_never_placeholder(db):
    """Leaderboard reset shows placeholder when mode is not NEVER."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        leaderboard_reset_mode=LeaderboardResetMode.MONTHLY,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.leaderboard_reset_hidden is False
    assert events.leaderboard_reset_placeholder is True
    assert events.next_leaderboard_reset is None


@pytest.mark.asyncio
async def test_revealed_anecdotes_count_for_last_published(db):
    """REVEALED anecdotes contribute to last_published_at calculation."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=1,
        days_off="",
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(db, GUILD_ID, 1, 2, "2026-07-13T15:00:00", "REVEALED")
    await _add_published_anecdote(db, GUILD_ID, 1, 2, "2026-07-14T15:00:00", "REVEALED")

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication == datetime(2026, 7, 15, 15, 0)


async def _add_player(db: aiosqlite.Connection, guild_id: int, user_id: int):
    """Insert a player row."""
    await Player.upsert(db, guild_id, user_id)


async def _add_published_anecdote(
    db: aiosqlite.Connection,
    guild_id: int,
    author: int,
    target: int,
    published_at: str,
    state: str,
):
    """Insert an anecdote with a published_at timestamp."""
    await db.execute(
        "INSERT INTO anecdotes (guild_id, author_id, target_id, content, state, published_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (guild_id, author, target, "test", state, published_at),
    )
    await db.commit()
