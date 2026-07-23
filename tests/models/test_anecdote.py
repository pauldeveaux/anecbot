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


@pytest_asyncio.fixture
async def author(db, guild):
    """Create an author player for anecdote references."""
    return await Player.upsert(db, 100, 1, can_submit=1)


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db, guild):
    """Anecdote.get returns None for nonexistent anecdote."""
    result = await Anecdote.get(db, 999)
    assert result is None


@pytest.mark.asyncio
async def test_create_with_defaults(db, author):
    """Anecdote.create creates row with default state and timestamps."""
    result = await Anecdote.create(
        db, guild_id=100, author_id=1, content="Test anecdote"
    )
    assert isinstance(result, Anecdote)
    assert result.id >= 1
    assert result.guild_id == 100
    assert result.author_id == 1
    assert result.content == "Test anecdote"
    assert result.state == "PENDING"
    assert result.created_at != ""
    assert result.published_at is None
    assert result.anecdote_message_id is None


@pytest.mark.asyncio
async def test_create_autoincrement(db, author):
    """Anecdote.create assigns incrementing IDs."""
    a1 = await Anecdote.create(db, guild_id=100, author_id=1, content="First")
    a2 = await Anecdote.create(db, guild_id=100, author_id=1, content="Second")
    assert a2.id == a1.id + 1


@pytest.mark.asyncio
async def test_upsert_updates_state(db, author):
    """Anecdote.upsert updates state and published_at."""
    anecdote = await Anecdote.create(db, guild_id=100, author_id=1, content="Test")
    updated = await Anecdote.update(
        db, anecdote.id, state="PUBLISHED", published_at="2026-01-01T12:00:00"
    )
    assert updated.state == "PUBLISHED"
    assert updated.published_at == "2026-01-01T12:00:00"
    assert updated.content == "Test"


@pytest.mark.asyncio
async def test_list_by_guild(db):
    """Anecdote.list filters by guild_id."""
    await Guild.upsert(db, 100)
    await Guild.upsert(db, 200)
    await Player.upsert(db, 100, 1, can_submit=1)
    await Player.upsert(db, 200, 3, can_submit=1)

    await Anecdote.create(db, guild_id=100, author_id=1, content="A")
    await Anecdote.create(db, guild_id=200, author_id=3, content="B")

    result = await Anecdote.list(db, guild_id=100)
    assert len(result) == 1
    assert result[0].content == "A"


@pytest.mark.asyncio
async def test_list_by_state(db, author):
    """Anecdote.list filters by state."""
    a1 = await Anecdote.create(db, guild_id=100, author_id=1, content="Pending")
    await Anecdote.create(db, guild_id=100, author_id=1, content="Also pending")
    await Anecdote.update(db, a1.id, state="PUBLISHED")

    pending = await Anecdote.list(db, state="PENDING")
    assert len(pending) == 1
    assert pending[0].content == "Also pending"


@pytest.mark.asyncio
async def test_delete_existing(db, author):
    """Anecdote.delete removes anecdote and returns True."""
    anecdote = await Anecdote.create(db, guild_id=100, author_id=1, content="Delete me")
    assert await Anecdote.delete(db, anecdote.id) is True
    assert await Anecdote.get(db, anecdote.id) is None


@pytest.mark.asyncio
async def test_delete_missing(db):
    """Anecdote.delete returns False for nonexistent anecdote."""
    assert await Anecdote.delete(db, 999) is False


@pytest.mark.asyncio
async def test_fk_constraint_guild(db):
    """Creating anecdote for nonexistent guild fails."""
    with pytest.raises(psycopg.IntegrityError):
        await Anecdote.create(db, guild_id=999, author_id=1, content="Bad")


@pytest.mark.asyncio
async def test_fk_constraint_author(db, guild):
    """Creating anecdote with nonexistent author fails."""
    with pytest.raises(psycopg.IntegrityError):
        await Anecdote.create(db, guild_id=100, author_id=999, content="Bad")


@pytest.mark.asyncio
async def test_cascade_delete_guild(db, author):
    """Deleting guild cascades to its anecdotes."""
    await Anecdote.create(db, guild_id=100, author_id=1, content="Cascade me")
    await Guild.delete(db, 100)
    result = await Anecdote.list(db, guild_id=100)
    assert len(result) == 0
