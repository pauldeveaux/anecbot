import pytest
import psycopg
import pytest_asyncio

from anecbot.models.anecdote import Anecdote
from anecbot.models.anecdote_choice import AnecdoteChoice
from anecbot.models.guild import Guild
from anecbot.models.player import Player


@pytest_asyncio.fixture
async def anecdote(db):
    """Create a guild, an author, and an anecdote to attach choices to."""
    await Guild.upsert(db, 100)
    await Player.upsert(db, 100, 1, can_submit=1)
    return await Anecdote.create(db, guild_id=100, author_id=1, content="x")


@pytest.mark.asyncio
async def test_get_returns_none_when_missing(db, anecdote):
    """AnecdoteChoice.get returns None for a nonexistent choice."""
    assert await AnecdoteChoice.get(db, 999) is None


@pytest.mark.asyncio
async def test_create_with_defaults(db, anecdote):
    """AnecdoteChoice.create inserts a row with the given label and correctness."""
    result = await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label="Le stagiaire", is_correct=1
    )
    assert isinstance(result, AnecdoteChoice)
    assert result.id >= 1
    assert result.anecdote_id == anecdote.id
    assert result.label == "Le stagiaire"
    assert result.is_correct == 1


@pytest.mark.asyncio
async def test_list_by_anecdote(db, anecdote):
    """AnecdoteChoice.list filters by anecdote_id."""
    await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label="Correct", is_correct=1
    )
    await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label="Wrong", is_correct=0
    )

    result = await AnecdoteChoice.list(db, anecdote_id=anecdote.id)
    assert len(result) == 2
    assert {c.label for c in result} == {"Correct", "Wrong"}


@pytest.mark.asyncio
async def test_fk_constraint_anecdote(db):
    """Creating a choice for a nonexistent anecdote fails."""
    with pytest.raises(psycopg.IntegrityError):
        await AnecdoteChoice.create(db, anecdote_id=999, label="x", is_correct=0)


@pytest.mark.asyncio
async def test_cascade_delete_anecdote(db, anecdote):
    """Deleting the anecdote cascades to its choices."""
    await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label="Correct", is_correct=1
    )
    await Anecdote.delete(db, anecdote.id)

    result = await AnecdoteChoice.list(db, anecdote_id=anecdote.id)
    assert result == []
