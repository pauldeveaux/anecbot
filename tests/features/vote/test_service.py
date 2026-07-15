from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.features.vote.service import record_vote
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.enums import VoteResult
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.models.vote import Vote

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
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


@pytest_asyncio.fixture
async def anecdote(db):
    """Create a guild, author, target, and a PUBLISHED anecdote."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)
    created = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    return await Anecdote.update(db, created.id, state="PUBLISHED")


@pytest.mark.asyncio
async def test_record_vote_saves_vote(db, anecdote):
    """A vote on a PUBLISHED anecdote is saved and RECORDED is returned."""
    result = await record_vote(db, anecdote.id, VOTER_ID, TARGET_ID)

    assert result == VoteResult.RECORDED
    vote = await Vote.get(db, anecdote.id, VOTER_ID)
    assert vote is not None
    assert vote.voted_for_id == TARGET_ID


@pytest.mark.asyncio
async def test_record_vote_auto_registers_unregistered_voter(db, anecdote):
    """An unregistered voter gets a bare Player row (no submit/target rights)."""
    assert await Player.get(db, GUILD_ID, VOTER_ID) is None

    await record_vote(db, anecdote.id, VOTER_ID, TARGET_ID)

    player = await Player.get(db, GUILD_ID, VOTER_ID)
    assert player is not None
    assert player.can_submit == 0
    assert player.can_be_target == 0


@pytest.mark.asyncio
async def test_record_vote_does_not_reregister_existing_player(db, anecdote):
    """An already-registered voter's existing flags are left untouched."""
    await Player.upsert(db, GUILD_ID, VOTER_ID, can_submit=1)

    await record_vote(db, anecdote.id, VOTER_ID, TARGET_ID)

    player = await Player.get(db, GUILD_ID, VOTER_ID)
    assert player is not None
    assert player.can_submit == 1


@pytest.mark.asyncio
async def test_record_vote_overwrites_previous_choice(db, anecdote):
    """Voting again changes the recorded choice rather than erroring."""
    other_target = 4
    await Player.upsert(db, GUILD_ID, other_target, can_be_target=1)

    await record_vote(db, anecdote.id, VOTER_ID, TARGET_ID)
    result = await record_vote(db, anecdote.id, VOTER_ID, other_target)

    assert result == VoteResult.RECORDED
    vote = await Vote.get(db, anecdote.id, VOTER_ID)
    assert vote is not None
    assert vote.voted_for_id == other_target


@pytest.mark.asyncio
async def test_record_vote_rejected_when_not_published(db):
    """Voting on a PENDING (not yet published) anecdote is rejected."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )

    result = await record_vote(db, pending.id, VOTER_ID, TARGET_ID)

    assert result == VoteResult.CLOSED
    assert await Vote.get(db, pending.id, VOTER_ID) is None


@pytest.mark.asyncio
async def test_record_vote_rejected_when_revealed(db, anecdote):
    """Voting on a REVEALED anecdote is rejected."""
    await Anecdote.update(db, anecdote.id, state="REVEALED")

    result = await record_vote(db, anecdote.id, VOTER_ID, TARGET_ID)

    assert result == VoteResult.CLOSED
    assert await Vote.get(db, anecdote.id, VOTER_ID) is None


@pytest.mark.asyncio
async def test_record_vote_rejected_when_anecdote_missing(db):
    """Voting on a nonexistent anecdote is rejected."""
    result = await record_vote(db, 999, VOTER_ID, TARGET_ID)

    assert result == VoteResult.CLOSED
