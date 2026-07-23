import pytest
import psycopg
import pytest_asyncio

from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.models.quality_vote import QualityVote


@pytest_asyncio.fixture
async def anecdote(db):
    """Create a guild, players, and anecdote for quality vote tests."""
    await Guild.upsert(db, 100)
    await Player.upsert(db, 100, 1, can_submit=1)
    await Player.upsert(db, 100, 2, can_be_target=1)
    return await Anecdote.create(db, guild_id=100, author_id=1, content="Test anecdote")


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db, anecdote):
    """QualityVote.get returns None for nonexistent vote."""
    result = await QualityVote.get(db, anecdote.id, 999)
    assert result is None


@pytest.mark.asyncio
async def test_upsert_creates_quality_vote(db, anecdote):
    """QualityVote.upsert creates a rating with default voted_at."""
    result = await QualityVote.upsert(db, anecdote.id, 10, rating=4, guild_id=100)
    assert isinstance(result, QualityVote)
    assert result.anecdote_id == anecdote.id
    assert result.user_id == 10
    assert result.rating == 4
    assert result.voted_at != ""


@pytest.mark.asyncio
async def test_upsert_one_rating_per_user(db, anecdote):
    """QualityVote.upsert overwrites previous rating for same user on same anecdote."""
    await QualityVote.upsert(db, anecdote.id, 10, rating=2, guild_id=100)
    updated = await QualityVote.upsert(db, anecdote.id, 10, rating=5, guild_id=100)
    assert updated.rating == 5

    votes = await QualityVote.list(db, anecdote_id=anecdote.id)
    assert len(votes) == 1


@pytest.mark.asyncio
async def test_list_by_anecdote(db, anecdote):
    """QualityVote.list filters by anecdote_id."""
    await QualityVote.upsert(db, anecdote.id, 10, rating=3, guild_id=100)
    await QualityVote.upsert(db, anecdote.id, 11, rating=5, guild_id=100)

    votes = await QualityVote.list(db, anecdote_id=anecdote.id)
    assert len(votes) == 2
    assert all(v.anecdote_id == anecdote.id for v in votes)


@pytest.mark.asyncio
async def test_delete_quality_vote(db, anecdote):
    """QualityVote.delete removes the rating and returns True."""
    await QualityVote.upsert(db, anecdote.id, 10, rating=3, guild_id=100)
    assert await QualityVote.delete(db, anecdote.id, 10) is True
    assert await QualityVote.get(db, anecdote.id, 10) is None


@pytest.mark.asyncio
async def test_delete_missing(db, anecdote):
    """QualityVote.delete returns False for nonexistent rating."""
    assert await QualityVote.delete(db, anecdote.id, 999) is False


@pytest.mark.asyncio
async def test_fk_constraint_anecdote(db):
    """Creating a rating for a nonexistent anecdote fails."""
    with pytest.raises(psycopg.IntegrityError):
        await QualityVote.upsert(db, 999, 10, rating=3, guild_id=100)


@pytest.mark.asyncio
async def test_rating_out_of_range_rejected(db, anecdote):
    """Ratings outside 1-5 are rejected by the CHECK constraint."""
    with pytest.raises(psycopg.IntegrityError):
        await QualityVote.upsert(db, anecdote.id, 10, rating=6, guild_id=100)


@pytest.mark.asyncio
async def test_cascade_delete_anecdote(db, anecdote):
    """Deleting the anecdote cascades to its quality votes."""
    await QualityVote.upsert(db, anecdote.id, 10, rating=3, guild_id=100)
    await QualityVote.upsert(db, anecdote.id, 11, rating=4, guild_id=100)
    await Anecdote.delete(db, anecdote.id)
    votes = await QualityVote.list(db, anecdote_id=anecdote.id)
    assert len(votes) == 0
