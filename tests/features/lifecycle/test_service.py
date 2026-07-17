from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.features.lifecycle.service import wipe_guild_data
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.enums import AnecdoteState
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
OTHER_GUILD_ID = 200
AUTHOR_ID = 1
TARGET_ID = 2
VOTER_ID = 3


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_wipe_guild_data_clears_everything_and_stops_game(db):
    """Votes, anecdotes, leaderboard entries, and players are all deleted; the game stops."""
    await Guild.upsert(db, GUILD_ID, started=1, started_at="2026-01-01T00:00:00")
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)
    anecdote = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="anecdote",
        state=AnecdoteState.PUBLISHED,
    )
    await Vote.upsert(db, anecdote.id, VOTER_ID, voted_for_id=TARGET_ID)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)

    await wipe_guild_data(db, GUILD_ID)

    assert await Anecdote.list(db, guild_id=GUILD_ID) == []
    assert await Player.list(db, guild_id=GUILD_ID) == []
    assert await LeaderboardEntry.list(db, guild_id=GUILD_ID) == []
    assert await Vote.list(db, anecdote_id=anecdote.id) == []
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    assert guild.started == 0
    assert guild.started_at is None


@pytest.mark.asyncio
async def test_wipe_guild_data_does_not_touch_other_guilds(db):
    """Only the target guild's data is deleted."""
    await Guild.upsert(db, GUILD_ID)
    await Guild.upsert(db, OTHER_GUILD_ID)
    await Player.upsert(db, OTHER_GUILD_ID, AUTHOR_ID, can_submit=1)

    await wipe_guild_data(db, GUILD_ID)

    other_players = await Player.list(db, guild_id=OTHER_GUILD_ID)
    assert len(other_players) == 1
