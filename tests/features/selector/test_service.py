import math
import random
from datetime import datetime
from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.features.selector.service import (
    compute_age_weight,
    compute_author_weight,
    compute_selection_probabilities,
    select_pending_anecdote,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
AUTHOR_ID = 1
PROLIFIC_AUTHOR_ID = 2
TARGET_ID = 3


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
    """Create a guild plus two authors and a target player."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, PROLIFIC_AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


async def _pending(
    db: aiosqlite.Connection, author_id: int, created_at: str
) -> Anecdote:
    """Create a PENDING anecdote with a fixed created_at."""
    return await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=author_id,
        target_id=TARGET_ID,
        content="x",
        created_at=created_at,
    )


async def _published(
    db: aiosqlite.Connection, author_id: int, published_at: str
) -> Anecdote:
    """Create a PUBLISHED anecdote with a fixed published_at."""
    created = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=author_id, target_id=TARGET_ID, content="x"
    )
    return await Anecdote.update(
        db, created.id, state="PUBLISHED", published_at=published_at
    )


# --- compute_age_weight ---


def test_compute_age_weight_same_day_is_one():
    """An anecdote submitted today has weight 1."""
    now = datetime(2026, 7, 15, 10, 0)
    assert compute_age_weight(now, now) == 1.0


def test_compute_age_weight_grows_with_sqrt_of_days():
    """N days waiting -> weight sqrt(N + 1), not linear."""
    created_at = datetime(2026, 7, 5, 10, 0)
    now = datetime(2026, 7, 15, 10, 0)  # 10 days later

    assert compute_age_weight(created_at, now) == pytest.approx(math.sqrt(11))


def test_compute_age_weight_never_negative_for_future_created_at():
    """A created_at somehow after now (clock skew) doesn't produce a negative weight."""
    created_at = datetime(2026, 7, 16, 10, 0)
    now = datetime(2026, 7, 15, 10, 0)

    assert compute_age_weight(created_at, now) == 1.0


def test_compute_age_weight_grows_slower_than_linear():
    """The sqrt curve is deliberately soft: 100 days doesn't weigh 100x a same-day one."""
    now = datetime(2026, 10, 15, 10, 0)
    created_at = datetime(2026, 7, 15, 10, 0)  # ~100 days earlier

    weight = compute_age_weight(created_at, now)

    assert weight < 15  # sqrt(101) ~= 10.05, nowhere near a linear 101x


# --- compute_author_weight ---


def test_compute_author_weight_no_history_is_neutral():
    """An author never published before gets no penalty."""
    assert compute_author_weight([], tau=5.0) == 1.0


def test_compute_author_weight_single_recent_publication_is_penalized():
    """A single very recent publication (distance 0) noticeably lowers the weight."""
    weight = compute_author_weight([0], tau=5.0)

    assert weight == pytest.approx(1 / (1 + math.exp(0)))
    assert weight < 1.0


def test_compute_author_weight_old_publication_barely_matters():
    """A publication far in the past (large distance) decays back toward neutral."""
    weight = compute_author_weight([1000], tau=5.0)

    assert weight == pytest.approx(1.0, abs=1e-6)


def test_compute_author_weight_multiple_recent_penalized_more_than_one():
    """Several recent publications stack up and penalize more than a single one."""
    single = compute_author_weight([0], tau=5.0)
    multiple = compute_author_weight([0, 1, 2], tau=5.0)

    assert multiple < single


def test_compute_author_weight_never_reaches_exactly_zero():
    """Even an extreme amount of recent activity keeps the weight strictly positive."""
    weight = compute_author_weight([0] * 1000, tau=5.0)

    assert weight > 0.0


# --- select_pending_anecdote ---


@pytest.mark.asyncio
async def test_select_pending_anecdote_returns_none_when_empty(db, players):
    """No PENDING anecdotes -> None."""
    now = datetime(2026, 7, 15, 10, 0)

    assert await select_pending_anecdote(db, GUILD_ID, now) is None


@pytest.mark.asyncio
async def test_select_pending_anecdote_single_candidate_always_wins(db, players):
    """With only one PENDING anecdote, it's always selected regardless of weight."""
    anecdote = await _pending(db, AUTHOR_ID, "2026-07-15T10:00:00")
    now = datetime(2026, 7, 15, 10, 0)

    result = await select_pending_anecdote(db, GUILD_ID, now)

    assert result is not None
    assert result.id == anecdote.id


@pytest.mark.asyncio
async def test_select_pending_anecdote_favors_older_and_less_recent_author(db, players):
    """A much-older anecdote from a never-published author strongly outweighs a same-day
    anecdote from a just-published, prolific author, across many deterministic draws."""
    favored = await _pending(db, AUTHOR_ID, "2026-01-01T00:00:00")
    await _pending(db, PROLIFIC_AUTHOR_ID, "2026-07-15T00:00:00")

    # The prolific author has just published several anecdotes very recently.
    await _published(db, PROLIFIC_AUTHOR_ID, "2026-07-13T00:00:00")
    await _published(db, PROLIFIC_AUTHOR_ID, "2026-07-14T00:00:00")
    await _published(db, PROLIFIC_AUTHOR_ID, "2026-07-15T00:00:00")

    now = datetime(2026, 7, 15, 0, 0)
    rng = random.Random(42)

    picks = [
        await select_pending_anecdote(db, GUILD_ID, now, rng=rng) for _ in range(50)
    ]

    favored_count = sum(1 for p in picks if p is not None and p.id == favored.id)
    assert favored_count > 45  # overwhelming majority of draws


@pytest.mark.asyncio
async def test_select_pending_anecdote_deterministic_with_seeded_rng(db, players):
    """The same seed produces the same sequence of picks."""
    await _pending(db, AUTHOR_ID, "2026-07-01T00:00:00")
    await _pending(db, PROLIFIC_AUTHOR_ID, "2026-07-10T00:00:00")
    now = datetime(2026, 7, 15, 0, 0)

    picks_a = [
        (await select_pending_anecdote(db, GUILD_ID, now, rng=random.Random(7))).id  # type: ignore[union-attr]
        for _ in range(20)
    ]
    picks_b = [
        (await select_pending_anecdote(db, GUILD_ID, now, rng=random.Random(7))).id  # type: ignore[union-attr]
        for _ in range(20)
    ]

    assert picks_a == picks_b


# --- compute_selection_probabilities ---


@pytest.mark.asyncio
async def test_compute_selection_probabilities_empty_queue(db, players):
    """No PENDING anecdotes -> empty dict."""
    now = datetime(2026, 7, 15, 10, 0)

    assert await compute_selection_probabilities(db, GUILD_ID, now) == {}


@pytest.mark.asyncio
async def test_compute_selection_probabilities_sum_to_one(db, players):
    """Probabilities across the whole PENDING queue always sum to 1."""
    await _pending(db, AUTHOR_ID, "2026-07-01T00:00:00")
    await _pending(db, PROLIFIC_AUTHOR_ID, "2026-07-10T00:00:00")
    await _pending(db, AUTHOR_ID, "2026-07-12T00:00:00")
    now = datetime(2026, 7, 15, 0, 0)

    probabilities = await compute_selection_probabilities(db, GUILD_ID, now)

    assert len(probabilities) == 3
    assert sum(probabilities.values()) == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_compute_selection_probabilities_single_candidate_is_certain(db, players):
    """A single PENDING anecdote has probability 1.0."""
    anecdote = await _pending(db, AUTHOR_ID, "2026-07-15T00:00:00")
    now = datetime(2026, 7, 15, 0, 0)

    probabilities = await compute_selection_probabilities(db, GUILD_ID, now)

    assert probabilities == {anecdote.id: pytest.approx(1.0)}


@pytest.mark.asyncio
async def test_compute_selection_probabilities_favors_older_less_recent_author(
    db, players
):
    """The older, never-published author's anecdote gets a higher probability."""
    favored = await _pending(db, AUTHOR_ID, "2026-01-01T00:00:00")
    recent = await _pending(db, PROLIFIC_AUTHOR_ID, "2026-07-15T00:00:00")
    await _published(db, PROLIFIC_AUTHOR_ID, "2026-07-14T00:00:00")
    now = datetime(2026, 7, 15, 0, 0)

    probabilities = await compute_selection_probabilities(db, GUILD_ID, now)

    assert probabilities[favored.id] > probabilities[recent.id]
