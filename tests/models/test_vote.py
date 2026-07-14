from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.models.vote import Vote

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def anecdote(db):
    """Create a guild, players, and anecdote for vote tests."""
    await Guild.upsert(db, 100)
    await Player.upsert(db, 100, 1, can_submit=1)
    await Player.upsert(db, 100, 2, can_be_target=1)
    return await Anecdote.create(
        db, guild_id=100, author_id=1, target_id=2, content="Test anecdote"
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db, anecdote):
    """Vote.get returns None for nonexistent vote."""
    result = await Vote.get(db, anecdote.id, 999)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_vote(db, anecdote):
    """Vote.upsert creates a vote with default voted_at."""
    result = await Vote.upsert(db, anecdote.id, 10, voted_for_id=2)
    assert isinstance(result, Vote)
    assert result.anecdote_id == anecdote.id
    assert result.user_id == 10
    assert result.voted_for_id == 2
    assert result.voted_at != ""


@pytest.mark.asyncio
async def test_upsert_one_vote_per_user(db, anecdote):
    """Vote.upsert overwrites previous vote for same user on same anecdote."""
    await Vote.upsert(db, anecdote.id, 10, voted_for_id=2)
    updated = await Vote.upsert(db, anecdote.id, 10, voted_for_id=1)
    assert updated.voted_for_id == 1

    votes = await Vote.list(db, anecdote_id=anecdote.id)
    assert len(votes) == 1


@pytest.mark.asyncio
async def test_list_by_anecdote(db, anecdote):
    """Vote.list filters by anecdote_id."""
    await Vote.upsert(db, anecdote.id, 10, voted_for_id=2)
    await Vote.upsert(db, anecdote.id, 11, voted_for_id=1)

    votes = await Vote.list(db, anecdote_id=anecdote.id)
    assert len(votes) == 2
    assert all(v.anecdote_id == anecdote.id for v in votes)


@pytest.mark.asyncio
async def test_delete_vote(db, anecdote):
    """Vote.delete removes vote and returns True."""
    await Vote.upsert(db, anecdote.id, 10, voted_for_id=2)
    assert await Vote.delete(db, anecdote.id, 10) is True
    assert await Vote.get(db, anecdote.id, 10) is None


@pytest.mark.asyncio
async def test_delete_missing(db, anecdote):
    """Vote.delete returns False for nonexistent vote."""
    assert await Vote.delete(db, anecdote.id, 999) is False


@pytest.mark.asyncio
async def test_fk_constraint_anecdote(db):
    """Creating vote for nonexistent anecdote fails."""
    with pytest.raises(aiosqlite.IntegrityError):
        await Vote.upsert(db, 999, 10, voted_for_id=2)


@pytest.mark.asyncio
async def test_cascade_delete_anecdote(db, anecdote):
    """Deleting anecdote cascades to its votes."""
    await Vote.upsert(db, anecdote.id, 10, voted_for_id=2)
    await Vote.upsert(db, anecdote.id, 11, voted_for_id=1)
    await Anecdote.delete(db, anecdote.id)
    votes = await Vote.list(db, anecdote_id=anecdote.id)
    assert len(votes) == 0
