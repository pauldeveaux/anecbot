import psycopg
import pytest

from anecbot.features.anecdote.service import create_anecdote, get_choices
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.quality_vote import QualityVote
from anecbot.models.vote import Vote
from anecbot.features.stats.service import get_guild_stats, get_player_stats

GUILD_ID = 100
AUTHOR_ID = 1
VOTER_ID = 2


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


async def _add_revealed_anecdote(
    db: psycopg.AsyncConnection, guild_id: int, author_id: int
) -> Anecdote:
    """Create an anecdote with MCQ choices, already REVEALED."""
    anecdote = await create_anecdote(
        db,
        guild_id,
        author_id,
        "test content",
        target_label="Target",
        choice_labels=["Wrong"],
    )
    return await Anecdote.update(db, anecdote.id, state=AnecdoteState.REVEALED)


@pytest.mark.asyncio
async def test_player_stats_empty_returns_zero_and_unranked(db):
    """A player with no data at all gets zeroed stats and no rank."""
    await Guild.upsert(db, GUILD_ID)
    stats = await get_player_stats(db, GUILD_ID, AUTHOR_ID)

    assert stats.points == 0
    assert stats.rank is None
    assert stats.revealed_count == 0
    assert stats.average_rating is None
    assert stats.votes_cast == 0
    assert stats.correct_votes == 0
    assert stats.accuracy_pct is None


@pytest.mark.asyncio
async def test_player_stats_points_and_rank(db):
    """Points and rank come from the leaderboard, ranked among all guild entries."""
    await Guild.upsert(db, GUILD_ID)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    await LeaderboardEntry.upsert(db, GUILD_ID, VOTER_ID, points=10)

    stats = await get_player_stats(db, GUILD_ID, AUTHOR_ID)

    assert stats.points == 5
    assert stats.rank == 2


@pytest.mark.asyncio
async def test_player_stats_revealed_count_excludes_other_states(db):
    """revealed_count only counts REVEALED anecdotes, never PENDING/PUBLISHED/REVEALING."""
    await Guild.upsert(db, GUILD_ID)
    await _add_player(db, GUILD_ID, AUTHOR_ID)
    await _add_anecdote(db, GUILD_ID, author=AUTHOR_ID, state="PENDING")
    await _add_anecdote(db, GUILD_ID, author=AUTHOR_ID, state="PUBLISHED")
    await _add_anecdote(db, GUILD_ID, author=AUTHOR_ID, state="REVEALING")
    await _add_revealed_anecdote(db, GUILD_ID, AUTHOR_ID)
    await _add_revealed_anecdote(db, GUILD_ID, AUTHOR_ID)

    stats = await get_player_stats(db, GUILD_ID, AUTHOR_ID)

    assert stats.revealed_count == 2


@pytest.mark.asyncio
async def test_player_stats_average_rating_excludes_non_revealed(db):
    """average_rating only counts ratings on the author's REVEALED anecdotes."""
    await Guild.upsert(db, GUILD_ID)
    await _add_player(db, GUILD_ID, AUTHOR_ID)
    revealed = await _add_revealed_anecdote(db, GUILD_ID, AUTHOR_ID)
    await QualityVote.upsert(db, revealed.id, VOTER_ID, rating=4, guild_id=GUILD_ID)

    published = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "not revealed yet",
        target_label="Target",
        choice_labels=["Wrong"],
    )
    await Anecdote.update(db, published.id, state=AnecdoteState.PUBLISHED)
    await QualityVote.upsert(db, published.id, VOTER_ID, rating=1, guild_id=GUILD_ID)

    stats = await get_player_stats(db, GUILD_ID, AUTHOR_ID)

    assert stats.average_rating == 4.0


@pytest.mark.asyncio
async def test_player_stats_average_rating_none_when_no_ratings(db):
    """average_rating is None when the author has revealed anecdotes but no ratings."""
    await Guild.upsert(db, GUILD_ID)
    await _add_player(db, GUILD_ID, AUTHOR_ID)
    await _add_revealed_anecdote(db, GUILD_ID, AUTHOR_ID)

    stats = await get_player_stats(db, GUILD_ID, AUTHOR_ID)

    assert stats.average_rating is None


@pytest.mark.asyncio
async def test_player_stats_votes_cast_and_correct_votes(db):
    """votes_cast counts all votes; correct_votes only those matching the anecdote's target."""
    await Guild.upsert(db, GUILD_ID)
    await _add_player(db, GUILD_ID, AUTHOR_ID)
    anecdote = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "test content",
        target_label="Target",
        choice_labels=["Wrong"],
    )
    choices = {c.label: c.id for c in await get_choices(db, anecdote.id)}

    other_anecdote = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "another anecdote",
        target_label="Target2",
        choice_labels=["Wrong2"],
    )
    other_choices = {c.label: c.id for c in await get_choices(db, other_anecdote.id)}

    await Vote.upsert(
        db,
        anecdote.id,
        VOTER_ID,
        voted_for_id=choices["Target"],
        guild_id=GUILD_ID,
    )
    await Vote.upsert(
        db,
        other_anecdote.id,
        VOTER_ID,
        voted_for_id=other_choices["Wrong2"],
        guild_id=GUILD_ID,
    )

    stats = await get_player_stats(db, GUILD_ID, VOTER_ID)

    assert stats.votes_cast == 2
    assert stats.correct_votes == 1
    assert stats.accuracy_pct == 50.0


@pytest.mark.asyncio
async def test_player_stats_accuracy_none_when_no_votes(db):
    """accuracy_pct is None (not a division by zero) when the player never voted."""
    await Guild.upsert(db, GUILD_ID)
    stats = await get_player_stats(db, GUILD_ID, VOTER_ID)

    assert stats.votes_cast == 0
    assert stats.accuracy_pct is None
