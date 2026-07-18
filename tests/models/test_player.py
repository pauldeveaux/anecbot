import pytest
import psycopg
import pytest_asyncio

from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.models.player import Player


@pytest_asyncio.fixture
async def guild(db):
    """Create a guild for foreign key references."""
    return await Guild.upsert(db, 100)


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db, guild):
    """Player.get returns None for a player that doesn't exist."""
    result = await Player.get(db, 100, 1)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_with_defaults(db, guild):
    """Player.upsert creates a row with default values."""
    result = await Player.upsert(db, 100, 1)
    assert isinstance(result, Player)
    assert result.guild_id == 100
    assert result.user_id == 1
    assert result.can_submit == 0
    assert result.can_be_target == 0
    assert result.suspended == 0
    assert result.registered_at != ""


@pytest.mark.asyncio
async def test_upsert_updates_flags(db, guild):
    """Player.upsert updates only the provided fields."""
    await Player.upsert(db, 100, 1)
    result = await Player.upsert(db, 100, 1, can_submit=1)
    assert result.can_submit == 1
    assert result.can_be_target == 0


@pytest.mark.asyncio
async def test_upsert_is_idempotent(db, guild):
    """Calling Player.upsert twice with same values gives same result."""
    first = await Player.upsert(db, 100, 1, can_submit=1)
    second = await Player.upsert(db, 100, 1, can_submit=1)
    assert first.can_submit == second.can_submit
    assert first.user_id == second.user_id


@pytest.mark.asyncio
async def test_list_filters_by_guild(db):
    """Player.list with guild_id filter returns only that guild's players."""
    await Guild.upsert(db, 100)
    await Guild.upsert(db, 200)
    await Player.upsert(db, 100, 1, can_submit=1)
    await Player.upsert(db, 100, 2, can_submit=1)
    await Player.upsert(db, 200, 3, can_submit=1)

    players = await Player.list(db, guild_id=100)
    assert len(players) == 2
    assert all(p.guild_id == 100 for p in players)


@pytest.mark.asyncio
async def test_same_user_multiple_guilds(db):
    """Same user_id can exist in multiple guilds independently."""
    await Guild.upsert(db, 100)
    await Guild.upsert(db, 200)
    await Player.upsert(db, 100, 1, can_submit=1)
    await Player.upsert(db, 200, 1, can_be_target=1)

    p1 = await Player.get(db, 100, 1)
    p2 = await Player.get(db, 200, 1)
    assert p1 is not None and p1.can_submit == 1 and p1.can_be_target == 0
    assert p2 is not None and p2.can_be_target == 1 and p2.can_submit == 0


@pytest.mark.asyncio
async def test_delete_removes_player(db, guild):
    """Player.delete removes player and returns True."""
    await Player.upsert(db, 100, 1)
    assert await Player.delete(db, 100, 1) is True
    assert await Player.get(db, 100, 1) is None


@pytest.mark.asyncio
async def test_delete_returns_false_when_missing(db, guild):
    """Player.delete returns False for nonexistent player."""
    assert await Player.delete(db, 100, 999) is False


@pytest.mark.asyncio
async def test_foreign_key_constraint(db):
    """Creating player for nonexistent guild fails."""
    with pytest.raises(psycopg.IntegrityError):
        await Player.upsert(db, 999, 1)


@pytest.mark.asyncio
async def test_cascade_delete_guild(db, guild):
    """Deleting guild cascades to its players."""
    await Player.upsert(db, 100, 1)
    await Player.upsert(db, 100, 2)
    await Guild.delete(db, 100)
    players = await Player.list(db, guild_id=100)
    assert len(players) == 0


@pytest.mark.asyncio
async def test_delete_fails_when_referenced_by_anecdote(db, guild):
    """Deleting a player still referenced by an anecdote raises IntegrityError.

    There's no ON DELETE CASCADE from anecdotes to players (by design — leaving a
    guild shouldn't erase anecdote history), so callers must check for existing
    anecdotes (features.anecdote.service.player_has_anecdotes) before deleting.
    """
    await Player.upsert(db, 100, 1)
    await Player.upsert(db, 100, 2)
    await Anecdote.create(db, guild_id=100, author_id=1, target_id=2, content="x")

    with pytest.raises(psycopg.IntegrityError):
        await Player.delete(db, 100, 1)
