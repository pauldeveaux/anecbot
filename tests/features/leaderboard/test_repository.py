import pytest

from anecbot.features.anecdote.service import create_anecdote, get_choices
from anecbot.features.leaderboard.repository import (
    count_correct_votes_by_user,
    count_revealed_by_author,
    count_votes_by_user,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.models.vote import Vote

GUILD_ID = 100
OTHER_GUILD_ID = 200
AUTHOR_ID = 1
VOTER_ID = 2
OTHER_VOTER_ID = 3


@pytest.mark.asyncio
async def test_count_votes_by_user_groups_and_orders_desc(db):
    """Votes are grouped per user and ranked by count descending."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID)
    anecdote = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "a", target_label="T", choice_labels=["W"]
    )
    other_anecdote = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "b", target_label="T2", choice_labels=["W2"]
    )
    choices = {c.label: c.id for c in await get_choices(db, anecdote.id)}
    other_choices = {c.label: c.id for c in await get_choices(db, other_anecdote.id)}

    await Vote.upsert(
        db, anecdote.id, VOTER_ID, voted_for_id=choices["T"], guild_id=GUILD_ID
    )
    await Vote.upsert(
        db,
        other_anecdote.id,
        VOTER_ID,
        voted_for_id=other_choices["W2"],
        guild_id=GUILD_ID,
    )
    await Vote.upsert(
        db,
        anecdote.id,
        OTHER_VOTER_ID,
        voted_for_id=choices["W"],
        guild_id=GUILD_ID,
    )

    rows = await count_votes_by_user(db, GUILD_ID)

    assert rows[0] == (VOTER_ID, 2)
    assert rows[1] == (OTHER_VOTER_ID, 1)


@pytest.mark.asyncio
async def test_count_votes_by_user_empty_guild_returns_empty(db):
    """No votes means an empty list, not an error."""
    await Guild.upsert(db, GUILD_ID)
    assert await count_votes_by_user(db, GUILD_ID) == []


@pytest.mark.asyncio
async def test_count_votes_by_user_isolated_by_guild(db):
    """Only the requested guild's votes are counted."""
    await Guild.upsert(db, GUILD_ID)
    await Guild.upsert(db, OTHER_GUILD_ID)
    await Player.upsert(db, OTHER_GUILD_ID, AUTHOR_ID)
    other_anecdote = await create_anecdote(
        db, OTHER_GUILD_ID, AUTHOR_ID, "a", target_label="T", choice_labels=["W"]
    )
    other_choices = {c.label: c.id for c in await get_choices(db, other_anecdote.id)}
    await Vote.upsert(
        db,
        other_anecdote.id,
        VOTER_ID,
        voted_for_id=other_choices["T"],
        guild_id=OTHER_GUILD_ID,
    )

    assert await count_votes_by_user(db, GUILD_ID) == []


@pytest.mark.asyncio
async def test_count_correct_votes_by_user_only_counts_matching_choice(db):
    """Only votes matching the anecdote's correct choice are counted."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID)
    anecdote = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "a", target_label="T", choice_labels=["W"]
    )
    choices = {c.label: c.id for c in await get_choices(db, anecdote.id)}

    await Vote.upsert(
        db, anecdote.id, VOTER_ID, voted_for_id=choices["T"], guild_id=GUILD_ID
    )
    await Vote.upsert(
        db,
        anecdote.id,
        OTHER_VOTER_ID,
        voted_for_id=choices["W"],
        guild_id=GUILD_ID,
    )

    correct = await count_correct_votes_by_user(db, GUILD_ID)

    assert correct == {VOTER_ID: 1}


@pytest.mark.asyncio
async def test_count_revealed_by_author_excludes_other_states(db):
    """Only REVEALED anecdotes count, never PENDING/PUBLISHED/REVEALING."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID)
    pending = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "a", target_label="T", choice_labels=["W"]
    )
    published = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "b", target_label="T", choice_labels=["W"]
    )
    revealed_one = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "c", target_label="T", choice_labels=["W"]
    )
    revealed_two = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "d", target_label="T", choice_labels=["W"]
    )
    await Anecdote.update(db, published.id, state=AnecdoteState.PUBLISHED)
    await Anecdote.update(db, revealed_one.id, state=AnecdoteState.REVEALED)
    await Anecdote.update(db, revealed_two.id, state=AnecdoteState.REVEALED)
    assert pending.state == AnecdoteState.PENDING

    rows = await count_revealed_by_author(db, GUILD_ID)

    assert rows == [(AUTHOR_ID, 2)]


@pytest.mark.asyncio
async def test_count_revealed_by_author_isolated_by_guild(db):
    """Only the requested guild's revealed anecdotes are counted."""
    await Guild.upsert(db, GUILD_ID)
    await Guild.upsert(db, OTHER_GUILD_ID)
    await Player.upsert(db, OTHER_GUILD_ID, AUTHOR_ID)
    other = await create_anecdote(
        db, OTHER_GUILD_ID, AUTHOR_ID, "a", target_label="T", choice_labels=["W"]
    )
    await Anecdote.update(db, other.id, state=AnecdoteState.REVEALED)

    assert await count_revealed_by_author(db, GUILD_ID) == []
