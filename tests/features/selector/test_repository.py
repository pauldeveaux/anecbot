import psycopg
import pytest
import pytest_asyncio

from anecbot.features.selector.repository import (
    count_total_published,
    get_author_publish_distances,
    get_author_publish_distances_bulk,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.models.player import Player

GUILD_ID = 100
OTHER_GUILD_ID = 200
AUTHOR_ID = 1
OTHER_AUTHOR_ID = 2
TARGET_ID = 3


@pytest_asyncio.fixture
async def players(db):
    """Create two guilds plus an author, another author, and a target player in each."""
    await Guild.upsert(db, GUILD_ID)
    await Guild.upsert(db, OTHER_GUILD_ID)
    for guild_id in (GUILD_ID, OTHER_GUILD_ID):
        await Player.upsert(db, guild_id, AUTHOR_ID, can_submit=1)
        await Player.upsert(db, guild_id, OTHER_AUTHOR_ID, can_submit=1)
        await Player.upsert(db, guild_id, TARGET_ID, can_be_target=1)


async def _anecdote(
    db: psycopg.AsyncConnection,
    guild_id: int,
    author_id: int,
    state: str = "PENDING",
    published_at: str | None = None,
) -> Anecdote:
    """Create an anecdote with the given state/published_at."""
    created = await Anecdote.create(
        db,
        guild_id=guild_id,
        author_id=author_id,
        target_id=TARGET_ID,
        content="x",
    )
    if state != "PENDING":
        return await Anecdote.update(
            db, created.id, state=state, published_at=published_at
        )
    return created


# --- count_total_published ---


@pytest.mark.asyncio
async def test_count_total_published_counts_published_and_revealed(db, players):
    """Both PUBLISHED and REVEALED anecdotes count."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "REVEALED", "2026-01-02T00:00:00")

    assert await count_total_published(db, GUILD_ID) == 2


@pytest.mark.asyncio
async def test_count_total_published_ignores_pending_and_running(db, players):
    """PENDING and RUNNING anecdotes don't count."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PENDING")
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "RUNNING")

    assert await count_total_published(db, GUILD_ID) == 0


@pytest.mark.asyncio
async def test_count_total_published_is_per_guild(db, players):
    """Anecdotes from another guild are never counted."""
    await _anecdote(db, OTHER_GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")

    assert await count_total_published(db, GUILD_ID) == 0


@pytest.mark.asyncio
async def test_count_total_published_zero_when_none(db, players):
    """No anecdotes at all -> zero."""
    assert await count_total_published(db, GUILD_ID) == 0


# --- get_author_publish_distances ---


@pytest.mark.asyncio
async def test_get_author_publish_distances_empty_when_never_published(db, players):
    """An author with no published anecdotes has no distances."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PENDING")

    assert await get_author_publish_distances(db, GUILD_ID, AUTHOR_ID) == []


@pytest.mark.asyncio
async def test_get_author_publish_distances_zero_for_most_recent(db, players):
    """The author's own most recent publication has distance 0 (nothing published since)."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")

    assert await get_author_publish_distances(db, GUILD_ID, AUTHOR_ID) == [0]


@pytest.mark.asyncio
async def test_get_author_publish_distances_counts_others_published_since(db, players):
    """Each of the author's anecdotes is counted against everything published after it."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")
    await _anecdote(db, GUILD_ID, OTHER_AUTHOR_ID, "PUBLISHED", "2026-01-02T00:00:00")
    await _anecdote(db, GUILD_ID, OTHER_AUTHOR_ID, "PUBLISHED", "2026-01-03T00:00:00")

    distances = await get_author_publish_distances(db, GUILD_ID, AUTHOR_ID)

    assert distances == [2]


@pytest.mark.asyncio
async def test_get_author_publish_distances_multiple_own_anecdotes(db, players):
    """Each of the author's own past anecdotes gets its own distance."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")
    await _anecdote(db, GUILD_ID, OTHER_AUTHOR_ID, "PUBLISHED", "2026-01-02T00:00:00")
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-03T00:00:00")

    distances = await get_author_publish_distances(db, GUILD_ID, AUTHOR_ID)

    assert sorted(distances) == [0, 2]


@pytest.mark.asyncio
async def test_get_author_publish_distances_ignores_pending(db, players):
    """A PENDING anecdote from the author isn't counted as a past publication."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PENDING")
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")

    assert await get_author_publish_distances(db, GUILD_ID, AUTHOR_ID) == [0]


@pytest.mark.asyncio
async def test_get_author_publish_distances_is_per_guild(db, players):
    """Publications in another guild never affect this guild's distances."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")
    await _anecdote(db, OTHER_GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-02T00:00:00")

    assert await get_author_publish_distances(db, GUILD_ID, AUTHOR_ID) == [0]


# --- get_author_publish_distances_bulk ---


@pytest.mark.asyncio
async def test_get_author_publish_distances_bulk_matches_single_author_calls(
    db, players
):
    """The batched result for several authors matches calling the single-author version each."""
    await _anecdote(db, GUILD_ID, AUTHOR_ID, "PUBLISHED", "2026-01-01T00:00:00")
    await _anecdote(db, GUILD_ID, OTHER_AUTHOR_ID, "PUBLISHED", "2026-01-02T00:00:00")
    await _anecdote(db, GUILD_ID, OTHER_AUTHOR_ID, "PUBLISHED", "2026-01-03T00:00:00")

    bulk = await get_author_publish_distances_bulk(
        db, GUILD_ID, [AUTHOR_ID, OTHER_AUTHOR_ID]
    )

    assert bulk[AUTHOR_ID] == await get_author_publish_distances(
        db, GUILD_ID, AUTHOR_ID
    )
    assert sorted(bulk[OTHER_AUTHOR_ID]) == sorted(
        await get_author_publish_distances(db, GUILD_ID, OTHER_AUTHOR_ID)
    )


@pytest.mark.asyncio
async def test_get_author_publish_distances_bulk_includes_authors_with_no_publications(
    db, players
):
    """An author with zero past publications still gets an empty list, not a missing key."""
    bulk = await get_author_publish_distances_bulk(
        db, GUILD_ID, [AUTHOR_ID, OTHER_AUTHOR_ID]
    )

    assert bulk == {AUTHOR_ID: [], OTHER_AUTHOR_ID: []}


@pytest.mark.asyncio
async def test_get_author_publish_distances_bulk_empty_author_list(db, players):
    """An empty author id list returns an empty dict without querying."""
    assert await get_author_publish_distances_bulk(db, GUILD_ID, []) == {}
