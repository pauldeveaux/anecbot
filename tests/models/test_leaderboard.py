import pytest
import psycopg
import pytest_asyncio

from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry


@pytest_asyncio.fixture
async def guild(db):
    """Create a guild for foreign key references."""
    return await Guild.upsert(db, 100)


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db, guild):
    """LeaderboardEntry.get returns None for nonexistent entry."""
    result = await LeaderboardEntry.get(db, 100, 999)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_with_default_points(db, guild):
    """LeaderboardEntry.upsert creates entry with 0 points."""
    result = await LeaderboardEntry.upsert(db, 100, 10)
    assert isinstance(result, LeaderboardEntry)
    assert result.guild_id == 100
    assert result.user_id == 10
    assert result.points == 0


@pytest.mark.asyncio
async def test_upsert_updates_points(db, guild):
    """LeaderboardEntry.upsert updates points."""
    await LeaderboardEntry.upsert(db, 100, 10)
    updated = await LeaderboardEntry.upsert(db, 100, 10, points=5)
    assert updated.points == 5


@pytest.mark.asyncio
async def test_list_by_guild(db):
    """LeaderboardEntry.list filters by guild_id."""
    await Guild.upsert(db, 100)
    await Guild.upsert(db, 200)
    await LeaderboardEntry.upsert(db, 100, 10, points=3)
    await LeaderboardEntry.upsert(db, 100, 11, points=7)
    await LeaderboardEntry.upsert(db, 200, 12, points=1)

    entries = await LeaderboardEntry.list(db, guild_id=100)
    assert len(entries) == 2
    assert all(e.guild_id == 100 for e in entries)


@pytest.mark.asyncio
async def test_delete_entry(db, guild):
    """LeaderboardEntry.delete removes entry and returns True."""
    await LeaderboardEntry.upsert(db, 100, 10, points=5)
    assert await LeaderboardEntry.delete(db, 100, 10) is True
    assert await LeaderboardEntry.get(db, 100, 10) is None


@pytest.mark.asyncio
async def test_delete_missing(db, guild):
    """LeaderboardEntry.delete returns False for nonexistent entry."""
    assert await LeaderboardEntry.delete(db, 100, 999) is False


@pytest.mark.asyncio
async def test_fk_constraint_guild(db):
    """Creating entry for nonexistent guild fails."""
    with pytest.raises(psycopg.IntegrityError):
        await LeaderboardEntry.upsert(db, 999, 10)


@pytest.mark.asyncio
async def test_cascade_delete_guild(db, guild):
    """Deleting guild cascades to its leaderboard entries."""
    await LeaderboardEntry.upsert(db, 100, 10, points=3)
    await LeaderboardEntry.upsert(db, 100, 11, points=7)
    await Guild.delete(db, 100)
    entries = await LeaderboardEntry.list(db, guild_id=100)
    assert len(entries) == 0
