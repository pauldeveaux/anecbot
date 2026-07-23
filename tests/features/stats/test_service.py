import psycopg
import pytest

from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.features.stats.service import get_guild_stats

GUILD_ID = 100


@pytest.mark.asyncio
async def test_stats_empty_guild(db):
    """Stats for a guild with no data returns zeroes."""
    stats = await get_guild_stats(db, GUILD_ID)
    assert stats.started is False
    assert stats.started_at is None
    assert stats.anecdotes_total == 0
    assert stats.anecdotes_pending == 0
    assert stats.anecdotes_published == 0
    assert stats.anecdotes_revealed == 0
    assert stats.players_total == 0
    assert stats.players_submitters == 0
    assert stats.players_targets == 0


@pytest.mark.asyncio
async def test_stats_with_guild_started(db):
    """Stats reflect started state and timestamp."""
    await Guild.upsert(db, GUILD_ID, started=1, started_at="2026-01-15T10:00:00+00:00")
    stats = await get_guild_stats(db, GUILD_ID)
    assert stats.started is True
    assert stats.started_at == "2026-01-15T10:00:00+00:00"


@pytest.mark.asyncio
async def test_stats_anecdote_counts(db):
    """Stats count anecdotes by state."""
    await Guild.upsert(db, GUILD_ID)
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)

    await _add_anecdote(db, GUILD_ID, author=1, state="PENDING")
    await _add_anecdote(db, GUILD_ID, author=1, state="PENDING")
    await _add_anecdote(db, GUILD_ID, author=1, state="PUBLISHED")
    await _add_anecdote(db, GUILD_ID, author=1, state="REVEALED")
    await _add_anecdote(db, GUILD_ID, author=1, state="REVEALED")
    await _add_anecdote(db, GUILD_ID, author=1, state="REVEALED")

    stats = await get_guild_stats(db, GUILD_ID)
    assert stats.anecdotes_total == 6
    assert stats.anecdotes_pending == 2
    assert stats.anecdotes_published == 1
    assert stats.anecdotes_revealed == 3


@pytest.mark.asyncio
async def test_stats_player_counts(db):
    """Stats count players by role."""
    await Guild.upsert(db, GUILD_ID)
    await _add_player(db, GUILD_ID, 1, can_submit=1, can_be_target=0)
    await _add_player(db, GUILD_ID, 2, can_submit=0, can_be_target=1)
    await _add_player(db, GUILD_ID, 3, can_submit=1, can_be_target=1)

    stats = await get_guild_stats(db, GUILD_ID)
    assert stats.players_total == 3
    assert stats.players_submitters == 2
    assert stats.players_targets == 2


@pytest.mark.asyncio
async def test_stats_isolated_by_guild(db):
    """Stats only count data for the requested guild."""
    other_guild = 999
    await Guild.upsert(db, GUILD_ID)
    await Guild.upsert(db, other_guild)
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, other_guild, 2)
    await _add_anecdote(db, other_guild, author=2, state="PENDING")

    stats = await get_guild_stats(db, GUILD_ID)
    assert stats.anecdotes_total == 0
    assert stats.players_total == 1


async def _add_player(
    db: psycopg.AsyncConnection,
    guild_id: int,
    user_id: int,
    can_submit: int = 0,
    can_be_target: int = 0,
):
    """Insert a player row."""
    await Player.upsert(
        db, guild_id, user_id, can_submit=can_submit, can_be_target=can_be_target
    )


async def _add_anecdote(
    db: psycopg.AsyncConnection,
    guild_id: int,
    author: int,
    state: str = "PENDING",
):
    """Insert an anecdote row."""
    await db.execute(
        "INSERT INTO anecdotes (guild_id, author_id, content, state) VALUES (%s, %s, %s, %s)",
        (guild_id, author, "test content", state),
    )
    await db.commit()
