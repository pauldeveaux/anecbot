from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.features.anecdote.service import create_anecdote, daily_limit_status
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
AUTHOR_ID = 1
TARGET_ID = 2


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
    """Create a guild with an author and a target player."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


@pytest.mark.asyncio
async def test_daily_limit_status_unlimited(db, players):
    """daily_limit=0 means unlimited — never reached regardless of count."""
    await Guild.upsert(db, GUILD_ID, daily_limit=0)
    for _ in range(5):
        await Anecdote.create(
            db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
        )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 0)


@pytest.mark.asyncio
async def test_daily_limit_status_under_limit(db, players):
    """Returns (False, limit) while the author is still under the configured limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=2)
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 2)


@pytest.mark.asyncio
async def test_daily_limit_status_at_limit(db, players):
    """Returns (True, limit) once the author has reached the configured limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=2)
    for _ in range(2):
        await Anecdote.create(
            db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
        )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (True, 2)


@pytest.mark.asyncio
async def test_daily_limit_status_ignores_other_authors(db, players):
    """Only the given author's submissions count toward their own limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=1)
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=3, target_id=TARGET_ID, content="x"
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 1)


@pytest.mark.asyncio
async def test_daily_limit_status_ignores_past_days(db, players):
    """Anecdotes created on a previous day don't count toward today's limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=1)
    await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="x",
        created_at="2020-01-01T00:00:00",
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 1)


@pytest.mark.asyncio
async def test_create_anecdote_defaults_to_pending(db, players):
    """create_anecdote saves the anecdote with state PENDING."""
    result = await create_anecdote(db, GUILD_ID, AUTHOR_ID, TARGET_ID, "Un truc drôle")

    assert result.state == "PENDING"
    assert result.guild_id == GUILD_ID
    assert result.author_id == AUTHOR_ID
    assert result.target_id == TARGET_ID
    assert result.content == "Un truc drôle"
