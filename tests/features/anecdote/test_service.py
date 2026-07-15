from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.features.anecdote.service import (
    create_anecdote,
    daily_limit_status,
    delete_anecdote,
    get_owned_pending_anecdote,
    get_pending_by_author,
    update_content,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
AUTHOR_ID = 1
TARGET_ID = 2


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
    """Create a guild with an author and a target player."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


@pytest.mark.asyncio
async def test_daily_limit_status_unlimited(db, players):
    """daily_limit=0 means unlimited — never reached regardless of count."""
    await Guild.upsert(db, GUILD_ID, daily_limit=0)
    for _ in range(5):
        await Anecdote.create(
            db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
        )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 0)


@pytest.mark.asyncio
async def test_daily_limit_status_under_limit(db, players):
    """Returns (False, limit) while the author is still under the configured limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=2)
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 2)


@pytest.mark.asyncio
async def test_daily_limit_status_at_limit(db, players):
    """Returns (True, limit) once the author has reached the configured limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=2)
    for _ in range(2):
        await Anecdote.create(
            db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
        )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (True, 2)


@pytest.mark.asyncio
async def test_daily_limit_status_ignores_other_authors(db, players):
    """Only the given author's submissions count toward their own limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=1)
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=3, target_id=TARGET_ID, content="x"
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 1)


@pytest.mark.asyncio
async def test_daily_limit_status_ignores_past_days(db, players):
    """Anecdotes created on a previous day don't count toward today's limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=1)
    await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="x",
        created_at="2020-01-01T00:00:00",
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 1)


@pytest.mark.asyncio
async def test_create_anecdote_defaults_to_pending(db, players):
    """create_anecdote saves the anecdote with state PENDING."""
    result = await create_anecdote(db, GUILD_ID, AUTHOR_ID, TARGET_ID, "Un truc drôle")

    assert result.state == "PENDING"
    assert result.guild_id == GUILD_ID
    assert result.author_id == AUTHOR_ID
    assert result.target_id == TARGET_ID
    assert result.content == "Un truc drôle"


@pytest.mark.asyncio
async def test_get_pending_by_author_only_pending(db, players):
    """Only PENDING anecdotes are returned, not published/revealed ones."""
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="P"
    )
    published = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Q"
    )
    await Anecdote.update(db, published.id, state="PUBLISHED")

    result = await get_pending_by_author(db, GUILD_ID, AUTHOR_ID)
    assert [a.id for a in result] == [pending.id]


@pytest.mark.asyncio
async def test_get_pending_by_author_only_own(db, players):
    """Only the given author's anecdotes are returned, not other authors'."""
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    mine = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Mine"
    )
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=3, target_id=TARGET_ID, content="Theirs"
    )

    result = await get_pending_by_author(db, GUILD_ID, AUTHOR_ID)
    assert [a.id for a in result] == [mine.id]


@pytest.mark.asyncio
async def test_get_pending_by_author_sorted_most_recent_first(db, players):
    """Anecdotes are returned newest first, by created_at then id as tiebreaker."""
    oldest = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Oldest",
        created_at="2026-01-01T10:00:00",
    )
    newest = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Newest",
        created_at="2026-01-03T10:00:00",
    )
    middle = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Middle",
        created_at="2026-01-02T10:00:00",
    )

    result = await get_pending_by_author(db, GUILD_ID, AUTHOR_ID)
    assert [a.id for a in result] == [newest.id, middle.id, oldest.id]


@pytest.mark.asyncio
async def test_update_content_changes_text(db, players):
    """update_content overwrites the anecdote's content."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Old"
    )

    result = await update_content(db, anecdote.id, "New")
    assert result.content == "New"
    assert result.state == "PENDING"


@pytest.mark.asyncio
async def test_delete_anecdote_removes_row(db, players):
    """delete_anecdote removes the row and returns True."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Bye"
    )

    assert await delete_anecdote(db, anecdote.id) is True
    assert await Anecdote.get(db, anecdote.id) is None


@pytest.mark.asyncio
async def test_delete_anecdote_missing_returns_false(db, players):
    """delete_anecdote returns False for a nonexistent id."""
    assert await delete_anecdote(db, 999) is False


@pytest.mark.asyncio
async def test_get_owned_pending_anecdote_returns_it(db, players):
    """Returns the anecdote when owned by author_id and still PENDING."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Mine"
    )

    result = await get_owned_pending_anecdote(db, anecdote.id, AUTHOR_ID)
    assert result is not None
    assert result.id == anecdote.id


@pytest.mark.asyncio
async def test_get_owned_pending_anecdote_none_when_missing(db, players):
    """Returns None for a nonexistent id."""
    assert await get_owned_pending_anecdote(db, 999, AUTHOR_ID) is None


@pytest.mark.asyncio
async def test_get_owned_pending_anecdote_none_when_not_owner(db, players):
    """Returns None when the anecdote belongs to a different author."""
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=3, target_id=TARGET_ID, content="Theirs"
    )

    assert await get_owned_pending_anecdote(db, anecdote.id, AUTHOR_ID) is None


@pytest.mark.asyncio
async def test_get_owned_pending_anecdote_none_when_not_pending(db, players):
    """Returns None once the anecdote is no longer PENDING (e.g. published)."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Mine"
    )
    await Anecdote.update(db, anecdote.id, state="PUBLISHED")

    assert await get_owned_pending_anecdote(db, anecdote.id, AUTHOR_ID) is None
