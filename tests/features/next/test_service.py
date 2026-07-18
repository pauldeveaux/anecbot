from datetime import datetime

import psycopg
import pytest

from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import GuildTimezone, LeaderboardResetMode
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.features.next.service import get_next_events

GUILD_ID = 100


@pytest.mark.asyncio
async def test_game_not_started(db):
    """No events when game is stopped."""
    await Guild.upsert(
        db, GUILD_ID, channel_id=1, started=0, timezone=GuildTimezone.UTC
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication is None
    assert events.next_reveal is None
    assert events.leaderboard_reset_hidden is True


@pytest.mark.asyncio
async def test_game_no_channel(db):
    """No events when no channel configured."""
    await Guild.upsert(db, GUILD_ID, started=1, timezone=GuildTimezone.UTC)
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication is None


@pytest.mark.asyncio
async def test_no_guild(db):
    """No events for unknown guild."""
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, 999, now)
    assert events.next_publication is None


@pytest.mark.asyncio
async def test_first_publication(db):
    """Next publication when no anecdotes published yet."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=1,
        timezone=GuildTimezone.UTC,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication == datetime(2026, 7, 15, 15, 0)


@pytest.mark.asyncio
async def test_publication_after_previous(db):
    """Next publication computed from last published anecdote."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=2,
        days_off="",
        timezone=GuildTimezone.UTC,
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(
        db, GUILD_ID, 1, 2, "2026-07-14T15:00:00", "PUBLISHED"
    )

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication == datetime(2026, 7, 16, 15, 0)


@pytest.mark.asyncio
async def test_reveal_after_publish_mode(db):
    """Next reveal for a PUBLISHED anecdote."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        reveal_interval_days=1,
        reveal_time="13:30",
        days_off="",
        timezone=GuildTimezone.UTC,
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(
        db, GUILD_ID, 1, 2, "2026-07-14T15:00:00", "PUBLISHED"
    )

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_reveal == datetime(2026, 7, 15, 13, 30)


@pytest.mark.asyncio
async def test_reveal_no_published_anecdotes(db):
    """No reveal when no anecdotes are awaiting reveal."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_reveal is None


@pytest.mark.asyncio
async def test_leaderboard_reset_never_hidden(db):
    """Leaderboard reset hidden when mode is NEVER."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        leaderboard_reset_mode=LeaderboardResetMode.NEVER,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.leaderboard_reset_hidden is True
    assert events.next_leaderboard_reset is None


@pytest.mark.asyncio
async def test_leaderboard_reset_non_never_computed(db):
    """Leaderboard reset computes a real next-reset datetime when mode is not NEVER."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        leaderboard_reset_mode=LeaderboardResetMode.MONTHLY,
        leaderboard_reset_anchor=1,
        timezone=GuildTimezone.UTC,
    )
    now = datetime(2026, 7, 15, 10, 0)  # day 15 > anchor 1 → next month
    events = await get_next_events(db, GUILD_ID, now)
    assert events.leaderboard_reset_hidden is False
    assert events.next_leaderboard_reset == datetime(2026, 8, 1, 0, 0)


@pytest.mark.asyncio
async def test_leaderboard_reset_uses_last_reset(db):
    """Leaderboard reset advances from last_leaderboard_reset_at once set."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        leaderboard_reset_mode=LeaderboardResetMode.MONTHLY,
        leaderboard_reset_anchor=1,
        last_leaderboard_reset_at="2026-07-01T00:00:00",
        timezone=GuildTimezone.UTC,
    )
    now = datetime(2026, 7, 15, 10, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_leaderboard_reset == datetime(2026, 8, 1, 0, 0)


@pytest.mark.asyncio
async def test_revealed_anecdotes_count_for_last_published(db):
    """REVEALED anecdotes contribute to last_published_at calculation."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=1,
        days_off="",
        timezone=GuildTimezone.UTC,
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(db, GUILD_ID, 1, 2, "2026-07-13T15:00:00", "REVEALED")
    await _add_published_anecdote(db, GUILD_ID, 1, 2, "2026-07-14T15:00:00", "REVEALED")

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.next_publication == datetime(2026, 7, 15, 15, 0)


@pytest.mark.asyncio
async def test_publication_overdue_when_queue_empty_and_past_publish_time(db):
    """publication_overdue is True once today's publish_time has passed with no pending anecdotes."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=1,
        days_off="",
        timezone=GuildTimezone.UTC,
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(
        db, GUILD_ID, 1, 2, "2026-07-01T15:00:00", "PUBLISHED"
    )

    before_time = datetime(2026, 7, 14, 10, 0)
    after_time = datetime(2026, 7, 14, 16, 0)

    events_before = await get_next_events(db, GUILD_ID, before_time)
    events_after = await get_next_events(db, GUILD_ID, after_time)

    assert events_before.publication_overdue is False
    assert events_after.publication_overdue is True


@pytest.mark.asyncio
async def test_publication_not_overdue_when_anecdotes_pending(db):
    """publication_overdue stays False when a pending anecdote exists, even past publish_time."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=1,
        started=1,
        publish_time="15:00",
        interval_days=1,
        days_off="",
        timezone=GuildTimezone.UTC,
    )
    await _add_player(db, GUILD_ID, 1)
    await _add_player(db, GUILD_ID, 2)
    await _add_published_anecdote(
        db, GUILD_ID, 1, 2, "2026-07-01T15:00:00", "PUBLISHED"
    )
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=1, target_id=2, content="pending"
    )

    now = datetime(2026, 7, 14, 16, 0)
    events = await get_next_events(db, GUILD_ID, now)
    assert events.publication_overdue is False


async def _add_player(db: psycopg.AsyncConnection, guild_id: int, user_id: int):
    """Insert a player row."""
    await Player.upsert(db, guild_id, user_id)


async def _add_published_anecdote(
    db: psycopg.AsyncConnection,
    guild_id: int,
    author: int,
    target: int,
    published_at: str,
    state: str,
):
    """Insert an anecdote with a published_at timestamp."""
    await db.execute(
        "INSERT INTO anecdotes (guild_id, author_id, target_id, content, state, published_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (guild_id, author, target, "test", state, published_at),
    )
    await db.commit()
