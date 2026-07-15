from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.models.database import run_migrations
from anecbot.models.enums import LeaderboardResetMode, RevealMode
from anecbot.models.guild import Guild

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db):
    """Guild.get returns None for a guild that doesn't exist."""
    result = await Guild.get(db, 123)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_with_defaults(db):
    """Guild.upsert creates a row with default values."""
    result = await Guild.upsert(db, 123)
    assert isinstance(result, Guild)
    assert result.guild_id == 123
    assert result.channel_id is None
    assert result.interval_days == 1
    assert result.publish_time == "15:00"
    assert result.days_off == ""
    assert result.reveal_mode == RevealMode.AFTER_PUBLISH
    assert result.reveal_interval_days == 1
    assert result.reveal_time == "13:30"
    assert result.leaderboard_reset_mode == LeaderboardResetMode.NEVER
    assert result.leaderboard_reset_interval == 1
    assert result.leaderboard_reset_anchor is None
    assert result.daily_limit == 0
    assert result.started_at is None


@pytest.mark.asyncio
async def test_upsert_updates_specific_fields(db):
    """Guild.upsert updates only the provided fields."""
    await Guild.upsert(db, 123)
    result = await Guild.upsert(db, 123, channel_id=456, interval_days=7)
    assert result.channel_id == 456
    assert result.interval_days == 7
    assert result.publish_time == "15:00"


@pytest.mark.asyncio
async def test_upsert_is_idempotent(db):
    """Calling Guild.upsert twice with same values gives same result."""
    first = await Guild.upsert(db, 123, daily_limit=5)
    second = await Guild.upsert(db, 123, daily_limit=5)
    assert first == second


@pytest.mark.asyncio
async def test_get_after_upsert(db):
    """Guild.get returns correct values after upsert."""
    await Guild.upsert(db, 123, channel_id=789, publish_time="10:00")
    result = await Guild.get(db, 123)
    assert result is not None
    assert result.guild_id == 123
    assert result.channel_id == 789
    assert result.publish_time == "10:00"


@pytest.mark.asyncio
async def test_upsert_updates_reveal_mode(db):
    """Guild.upsert updates and persists reveal_mode."""
    await Guild.upsert(db, 123)
    result = await Guild.upsert(db, 123, reveal_mode=RevealMode.INTERVAL)
    assert result.reveal_mode == RevealMode.INTERVAL
    fetched = await Guild.get(db, 123)
    assert fetched is not None
    assert fetched.reveal_mode == RevealMode.INTERVAL


@pytest.mark.asyncio
async def test_upsert_updates_leaderboard_reset_fields(db):
    """Guild.upsert updates and persists leaderboard reset mode/interval/anchor."""
    await Guild.upsert(db, 123)
    result = await Guild.upsert(
        db,
        123,
        leaderboard_reset_mode=LeaderboardResetMode.MONTHLY,
        leaderboard_reset_interval=2,
        leaderboard_reset_anchor=1,
    )
    assert result.leaderboard_reset_mode == LeaderboardResetMode.MONTHLY
    assert result.leaderboard_reset_interval == 2
    assert result.leaderboard_reset_anchor == 1
    fetched = await Guild.get(db, 123)
    assert fetched is not None
    assert fetched.leaderboard_reset_mode == LeaderboardResetMode.MONTHLY
    assert fetched.leaderboard_reset_interval == 2
    assert fetched.leaderboard_reset_anchor == 1


@pytest.mark.asyncio
async def test_upsert_rejects_unknown_column(db):
    """Guild.upsert raises ValueError for unknown columns."""
    with pytest.raises(ValueError, match="Unknown column"):
        await Guild.upsert(db, 123, bogus_field=42)
