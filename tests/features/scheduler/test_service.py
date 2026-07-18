from datetime import datetime
from typing import cast
from zoneinfo import ZoneInfo

import discord
import psycopg
import pytest
import pytest_asyncio

from anecbot.features.scheduler.service import (
    check_leaderboard_reset_for_guild,
    check_leaderboard_resets,
    check_publication_for_guild,
    check_publications,
    check_reveal_for_guild,
    check_reveals,
    is_leaderboard_reset_due,
    is_publication_due,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import LeaderboardResetMode
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player

GUILD_ID = 100
OTHER_GUILD_ID = 200
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2
VOTER_ID = 3

WEEKEND = {5, 6}  # Saturday, Sunday
PARIS = ZoneInfo("Europe/Paris")


class _FakeMessage:
    """Stand-in for a sent discord.Message — .id is read, .edit() calls are recorded."""

    def __init__(self, message_id: int):
        self.id = message_id

    async def edit(self, **kwargs: object) -> None:
        """No-op edit for scheduler tests — only publish_and_open_voting's side effects matter."""

    async def reply(self, embed: discord.Embed | None = None) -> "_FakeMessage":
        """Return a new fake message, standing in for a reveal reply."""
        return _FakeMessage(message_id=self.id + 1)


class _FakeChannel:
    """Stand-in for a Messageable channel — records sends, returns fake messages."""

    def __init__(self, messages: dict[int, _FakeMessage] | None = None):
        self.sent_embeds: list[discord.Embed | None] = []
        self._messages: dict[int, _FakeMessage] = messages or {}

    async def send(self, *, embed: discord.Embed | None = None) -> _FakeMessage:
        """Record the send and return a fake message with a fixed id."""
        self.sent_embeds.append(embed)
        message = _FakeMessage(message_id=999)
        self._messages[message.id] = message
        return message

    async def fetch_message(self, message_id: int) -> _FakeMessage:
        """Return the previously sent fake message matching the id."""
        return self._messages[message_id]


class _FakeGuild:
    """Stand-in for discord.Guild — only get_member is used (via display_name)."""

    def __init__(self, guild_id: int):
        self.id = guild_id

    def get_member(self, user_id: int) -> None:
        """No cached members in tests — display_name falls back to the user id."""
        return None


class _FakeBot:
    """Stand-in for discord.Client — get_channel/get_guild are used by the service."""

    def __init__(self, channels: dict[int, _FakeChannel]):
        self._channels = channels

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """Return a fake discord.Guild for any id."""
        return _FakeGuild(guild_id)


@pytest_asyncio.fixture
async def players(db):
    """Create a guild (started, with a channel) plus an author and a target player."""
    await Guild.upsert(
        db, GUILD_ID, channel_id=CHANNEL_ID, started=1, publish_time="15:00"
    )
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


# --- is_publication_due — never published before ---


def test_is_publication_due_first_time_active_day_time_reached():
    """Never published, active day, current time past publish_time → due."""
    now = datetime(2026, 7, 13, 15, 0)  # Monday 15:00
    assert is_publication_due(None, 1, "15:00", set(), now) is True


def test_is_publication_due_first_time_time_not_reached():
    """Never published, active day, current time before publish_time → not due."""
    now = datetime(2026, 7, 13, 10, 0)  # Monday 10:00
    assert is_publication_due(None, 1, "15:00", set(), now) is False


def test_is_publication_due_first_time_day_off():
    """Never published, today is a day off → not due, regardless of time."""
    now = datetime(2026, 7, 18, 16, 0)  # Saturday 16:00
    assert is_publication_due(None, 1, "15:00", WEEKEND, now) is False


# --- is_publication_due — subsequent ---


def test_is_publication_due_subsequent_reached():
    """Interval elapsed and target time reached → due."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday
    now = datetime(2026, 7, 14, 15, 0)  # Tuesday, interval=1 → due at 15:00
    assert is_publication_due(last, 1, "15:00", set(), now) is True


def test_is_publication_due_subsequent_not_yet():
    """Interval elapsed but target time not reached yet → not due."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday
    now = datetime(2026, 7, 14, 10, 0)  # Tuesday 10:00, before 15:00
    assert is_publication_due(last, 1, "15:00", set(), now) is False


def test_is_publication_due_subsequent_interval_not_elapsed():
    """Interval not elapsed yet → not due even if time-of-day matches."""
    last = datetime(2026, 7, 13, 15, 0)  # Monday
    now = datetime(2026, 7, 13, 16, 0)  # Same day, interval=2 not elapsed
    assert is_publication_due(last, 2, "15:00", set(), now) is False


def test_is_publication_due_catch_up_after_long_offline():
    """A long-overdue publication only fires once today's publish_time is reached."""
    last = datetime(2026, 7, 1, 15, 0)  # Two weeks ago
    before_time = datetime(2026, 7, 14, 10, 0)
    after_time = datetime(2026, 7, 14, 16, 0)
    assert is_publication_due(last, 1, "15:00", set(), before_time) is False
    assert is_publication_due(last, 1, "15:00", set(), after_time) is True


def test_is_publication_due_respects_timezone_across_midnight():
    """A last_published moment landing on a different local calendar day changes the due date."""
    last = datetime(2026, 7, 13, 23, 0)  # 23:00 UTC Monday = 01:00 CEST Tuesday
    # local last_published date is Tuesday 07-14 -> next active day (+1) = Wednesday 07-15
    # 15:00 Paris (CEST) = 13:00 UTC
    just_before = datetime(2026, 7, 15, 12, 55)
    just_after = datetime(2026, 7, 15, 13, 5)

    assert is_publication_due(last, 1, "15:00", set(), just_before, PARIS) is False
    assert is_publication_due(last, 1, "15:00", set(), just_after, PARIS) is True
    # a plain UTC interpretation would already treat Jul 14 as the target day,
    # so it's due a full day earlier than the correct Paris-local Jul 15 target
    naive_utc_next_day = datetime(2026, 7, 14, 16, 0)
    assert is_publication_due(last, 1, "15:00", set(), naive_utc_next_day) is True


# --- check_publication_for_guild ---


@pytest.mark.asyncio
async def test_check_publication_for_guild_skips_when_not_started(db):
    """A guild with started=0 is never checked, regardless of timing."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID, started=0)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publication_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is False
    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_check_publication_for_guild_skips_when_no_channel(db):
    """A guild with no channel configured is never checked."""
    await Guild.upsert(db, GUILD_ID, started=1)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    triggered = await check_publication_for_guild(
        cast(discord.Client, _FakeBot({})), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is False


@pytest.mark.asyncio
async def test_check_publication_for_guild_skips_when_not_due(db, players):
    """Nothing is published if the publication isn't due yet."""
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publication_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 10, 0)
    )

    assert triggered is False
    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_check_publication_for_guild_triggers_when_due(db, players):
    """A due, started guild with a pending anecdote gets published."""
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publication_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is True
    assert len(channel.sent_embeds) == 1


# --- check_publications ---


@pytest.mark.asyncio
async def test_check_publications_only_checks_started_guilds(db, players):
    """A stopped guild is skipped even if otherwise due."""
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    await Guild.upsert(db, OTHER_GUILD_ID, channel_id=CHANNEL_ID, started=0)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publications(
        cast(discord.Client, bot), db, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered == 1
    assert len(channel.sent_embeds) == 1


@pytest.mark.asyncio
async def test_check_publications_continues_after_guild_failure(db, players):
    """A guild whose publish attempt raises doesn't stop other guilds from being checked."""
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="boom"
    )
    other_channel_id = 777
    await Guild.upsert(
        db, OTHER_GUILD_ID, channel_id=other_channel_id, started=1, publish_time="15:00"
    )
    await Player.upsert(db, OTHER_GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, OTHER_GUILD_ID, TARGET_ID, can_be_target=1)
    await Anecdote.create(
        db,
        guild_id=OTHER_GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="ok",
    )
    other_channel = _FakeChannel()
    # GUILD_ID's own channel (CHANNEL_ID) is deliberately not registered with the fake bot,
    # so its publish attempt raises inside publish_next_anecdote's channel assertion.
    bot = _FakeBot({other_channel_id: other_channel})

    triggered = await check_publications(
        cast(discord.Client, bot), db, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered == 1
    assert len(other_channel.sent_embeds) == 1


# --- check_reveal_for_guild / check_reveals ---


async def _published_anecdote(
    db: psycopg.AsyncConnection,
    published_at: str,
    message_id: int = 999,
    guild_id: int = GUILD_ID,
) -> Anecdote:
    """Insert a PUBLISHED anecdote with a fixed published_at and message id."""
    created = await Anecdote.create(
        db, guild_id=guild_id, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    return await Anecdote.update(
        db,
        created.id,
        state="PUBLISHED",
        published_at=published_at,
        anecdote_message_id=message_id,
    )


@pytest.mark.asyncio
async def test_check_reveal_for_guild_skips_when_not_started(db, players):
    """A guild with started=0 is never revealed, regardless of timing."""
    await _published_anecdote(db, "2026-07-13T15:00:00")
    await Guild.upsert(db, GUILD_ID, started=0)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel({999: _FakeMessage(999)})
    bot = _FakeBot({CHANNEL_ID: channel})

    revealed = await check_reveal_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 14, 14, 0)
    )

    assert revealed == 0


@pytest.mark.asyncio
async def test_check_reveal_for_guild_skips_when_no_channel(db):
    """A guild with no channel configured is never revealed."""
    await Guild.upsert(db, GUILD_ID, started=1)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    revealed = await check_reveal_for_guild(
        cast(discord.Client, _FakeBot({})), db, guild, datetime(2026, 7, 14, 14, 0)
    )

    assert revealed == 0


@pytest.mark.asyncio
async def test_check_reveal_for_guild_reveals_due_anecdotes(db, players):
    """A due anecdote in a started guild with a channel is revealed."""
    await _published_anecdote(db, "2026-07-13T15:00:00")
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel({999: _FakeMessage(999)})
    bot = _FakeBot({CHANNEL_ID: channel})

    revealed = await check_reveal_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 14, 14, 0)
    )

    assert revealed == 1
    stored = await Anecdote.list(db, guild_id=GUILD_ID, state="REVEALED")
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_check_reveals_sums_across_started_guilds(db, players):
    """A stopped guild is skipped, but a started one contributes to the total."""
    await _published_anecdote(db, "2026-07-13T15:00:00")
    await Guild.upsert(db, OTHER_GUILD_ID, channel_id=CHANNEL_ID, started=0)
    channel = _FakeChannel({999: _FakeMessage(999)})
    bot = _FakeBot({CHANNEL_ID: channel})

    total = await check_reveals(
        cast(discord.Client, bot), db, datetime(2026, 7, 14, 14, 0)
    )

    assert total == 1


@pytest.mark.asyncio
async def test_check_reveals_continues_after_guild_failure(db, players):
    """A guild whose reveal attempt raises doesn't stop other guilds from being revealed."""
    await _published_anecdote(db, "2026-07-13T15:00:00")

    other_channel_id = 777
    await Guild.upsert(db, OTHER_GUILD_ID, channel_id=other_channel_id, started=1)
    await Player.upsert(db, OTHER_GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, OTHER_GUILD_ID, TARGET_ID, can_be_target=1)
    await _published_anecdote(
        db, "2026-07-13T15:00:00", message_id=888, guild_id=OTHER_GUILD_ID
    )

    other_channel = _FakeChannel({888: _FakeMessage(888)})
    # GUILD_ID's own channel (CHANNEL_ID) is deliberately not registered, so its reveal raises.
    bot = _FakeBot({other_channel_id: other_channel})

    total = await check_reveals(
        cast(discord.Client, bot), db, datetime(2026, 7, 14, 14, 0)
    )

    assert total == 1
    stored = await Anecdote.list(db, guild_id=OTHER_GUILD_ID, state="REVEALED")
    assert len(stored) == 1


# --- is_leaderboard_reset_due ---


def test_is_leaderboard_reset_due_never_mode_always_false():
    """NEVER mode is never due, regardless of last reset or timing."""
    now = datetime(2026, 7, 13, 15, 0)
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.NEVER, 1, None, "00:00", now
        )
        is False
    )


def test_is_leaderboard_reset_due_daily_first_time():
    """Never reset before, DAILY mode, reset time already passed today → due."""
    now = datetime(2026, 7, 13, 15, 0)
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.DAILY, 1, None, "00:00", now
        )
        is True
    )


def test_is_leaderboard_reset_due_daily_subsequent():
    """Interval elapsed and reset_time reached → due; time not yet reached → not due."""
    last = datetime(2026, 7, 13, 15, 0)
    elapsed = datetime(2026, 7, 14, 16, 0)
    not_elapsed = datetime(2026, 7, 14, 10, 0)
    assert (
        is_leaderboard_reset_due(
            last, LeaderboardResetMode.DAILY, 1, None, "15:00", elapsed
        )
        is True
    )
    assert (
        is_leaderboard_reset_due(
            last, LeaderboardResetMode.DAILY, 1, None, "15:00", not_elapsed
        )
        is False
    )


def test_is_leaderboard_reset_due_weekly_first_time_anchor_reached():
    """Never reset, WEEKLY mode, today is on/after this week's anchor weekday → due."""
    # Monday 2026-07-13, anchor=2 (Wednesday) reached on Wednesday 2026-07-15
    now = datetime(2026, 7, 15, 0, 0)
    assert (
        is_leaderboard_reset_due(None, LeaderboardResetMode.WEEKLY, 1, 2, "00:00", now)
        is True
    )


def test_is_leaderboard_reset_due_weekly_first_time_anchor_not_reached():
    """Never reset, WEEKLY mode, anchor weekday not reached yet this week → not due."""
    now = datetime(2026, 7, 14, 0, 0)  # Tuesday, anchor=2 (Wednesday) not reached
    assert (
        is_leaderboard_reset_due(None, LeaderboardResetMode.WEEKLY, 1, 2, "00:00", now)
        is False
    )


def test_is_leaderboard_reset_due_weekly_subsequent():
    """Interval elapsed in weeks → due."""
    last = datetime(2026, 7, 13, 0, 0)
    due = datetime(2026, 7, 20, 0, 0)
    not_due = datetime(2026, 7, 19, 0, 0)
    assert (
        is_leaderboard_reset_due(last, LeaderboardResetMode.WEEKLY, 1, 2, "00:00", due)
        is True
    )
    assert (
        is_leaderboard_reset_due(
            last, LeaderboardResetMode.WEEKLY, 1, 2, "00:00", not_due
        )
        is False
    )


def test_is_leaderboard_reset_due_monthly_first_time():
    """Never reset, MONTHLY mode, today on/after the anchor day-of-month → due."""
    now = datetime(2026, 7, 15, 0, 0)
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.MONTHLY, 1, 15, "00:00", now
        )
        is True
    )
    earlier = datetime(2026, 7, 10, 0, 0)
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.MONTHLY, 1, 15, "00:00", earlier
        )
        is False
    )


def test_is_leaderboard_reset_due_monthly_subsequent():
    """Interval elapsed in months → due."""
    last = datetime(2026, 6, 15, 0, 0)
    due = datetime(2026, 7, 15, 0, 0)
    not_due = datetime(2026, 7, 10, 0, 0)
    assert (
        is_leaderboard_reset_due(
            last, LeaderboardResetMode.MONTHLY, 1, 15, "00:00", due
        )
        is True
    )
    assert (
        is_leaderboard_reset_due(
            last, LeaderboardResetMode.MONTHLY, 1, 15, "00:00", not_due
        )
        is False
    )


def test_is_leaderboard_reset_due_yearly_first_time():
    """Never reset, YEARLY mode, today on/after the anchor day-of-year → due."""
    now = datetime(2026, 1, 15, 0, 0)  # day 15 of the year
    assert (
        is_leaderboard_reset_due(None, LeaderboardResetMode.YEARLY, 1, 15, "00:00", now)
        is True
    )
    earlier = datetime(2026, 1, 10, 0, 0)
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.YEARLY, 1, 15, "00:00", earlier
        )
        is False
    )


def test_is_leaderboard_reset_due_yearly_subsequent():
    """Interval elapsed in years → due."""
    last = datetime(2025, 1, 15, 0, 0)
    due = datetime(2026, 1, 15, 0, 0)
    not_due = datetime(2025, 6, 1, 0, 0)
    assert (
        is_leaderboard_reset_due(last, LeaderboardResetMode.YEARLY, 1, 15, "00:00", due)
        is True
    )
    assert (
        is_leaderboard_reset_due(
            last, LeaderboardResetMode.YEARLY, 1, 15, "00:00", not_due
        )
        is False
    )


def test_is_leaderboard_reset_due_at_configured_time():
    """The configured reset_time is used instead of always defaulting to midnight."""
    now_before = datetime(2026, 7, 15, 18, 0)
    now_after = datetime(2026, 7, 15, 19, 0)
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.MONTHLY, 1, 15, "18:30", now_before
        )
        is False
    )
    assert (
        is_leaderboard_reset_due(
            None, LeaderboardResetMode.MONTHLY, 1, 15, "18:30", now_after
        )
        is True
    )


# --- check_leaderboard_reset_for_guild / check_leaderboard_resets ---


@pytest.mark.asyncio
async def test_check_leaderboard_reset_for_guild_skips_when_never_mode(db, players):
    """The default NEVER mode never triggers a reset."""
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_leaderboard_reset_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is False
    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_check_leaderboard_reset_for_guild_skips_when_not_started(db, players):
    """A guild with started=0 is never reset, regardless of timing."""
    await Guild.upsert(
        db, GUILD_ID, started=0, leaderboard_reset_mode=LeaderboardResetMode.DAILY
    )
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_leaderboard_reset_for_guild(
        cast(discord.Client, bot), db, guild, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered is False


@pytest.mark.asyncio
async def test_check_leaderboard_reset_for_guild_publishes_then_resets(db, players):
    """A due reset first publishes the current standings, then clears the leaderboard."""
    await Guild.upsert(db, GUILD_ID, leaderboard_reset_mode=LeaderboardResetMode.DAILY)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    now = datetime(2026, 7, 13, 15, 0)

    triggered = await check_leaderboard_reset_for_guild(
        cast(discord.Client, bot), db, guild, now
    )

    assert triggered is True
    assert len(channel.sent_embeds) == 1
    assert await LeaderboardEntry.list(db, guild_id=GUILD_ID) == []
    updated = await Guild.get(db, GUILD_ID)
    assert updated is not None
    assert updated.last_leaderboard_reset_at == now.isoformat()
    assert updated.leaderboard_reset_in_progress == 0
    assert updated.leaderboard_reset_published == 0


@pytest.mark.asyncio
async def test_check_leaderboard_reset_resumes_without_republishing_when_already_sent(
    db, players
):
    """A crash after the standings were published but before the reset completed doesn't repost."""
    await Guild.upsert(
        db,
        GUILD_ID,
        leaderboard_reset_mode=LeaderboardResetMode.DAILY,
        leaderboard_reset_in_progress=1,
        leaderboard_reset_published=1,
    )
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    now = datetime(2026, 7, 13, 15, 0)

    triggered = await check_leaderboard_reset_for_guild(
        cast(discord.Client, bot), db, guild, now
    )

    assert triggered is True
    assert channel.sent_embeds == []
    assert await LeaderboardEntry.list(db, guild_id=GUILD_ID) == []
    updated = await Guild.get(db, GUILD_ID)
    assert updated is not None
    assert updated.leaderboard_reset_in_progress == 0
    assert updated.leaderboard_reset_published == 0


@pytest.mark.asyncio
async def test_check_leaderboard_reset_resumes_and_publishes_when_not_yet_sent(
    db, players
):
    """A crash claimed but before publishing resumes by publishing once, then resetting."""
    await Guild.upsert(
        db,
        GUILD_ID,
        leaderboard_reset_mode=LeaderboardResetMode.DAILY,
        leaderboard_reset_in_progress=1,
        leaderboard_reset_published=0,
    )
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    now = datetime(2026, 7, 13, 15, 0)

    triggered = await check_leaderboard_reset_for_guild(
        cast(discord.Client, bot), db, guild, now
    )

    assert triggered is True
    assert len(channel.sent_embeds) == 1
    assert await LeaderboardEntry.list(db, guild_id=GUILD_ID) == []


@pytest.mark.asyncio
async def test_check_leaderboard_resets_only_checks_started_guilds(db, players):
    """A stopped guild is skipped even if its reset would otherwise be due."""
    await Guild.upsert(db, GUILD_ID, leaderboard_reset_mode=LeaderboardResetMode.DAILY)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    await Guild.upsert(
        db,
        OTHER_GUILD_ID,
        channel_id=CHANNEL_ID,
        started=0,
        leaderboard_reset_mode=LeaderboardResetMode.DAILY,
    )
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_leaderboard_resets(
        cast(discord.Client, bot), db, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered == 1


@pytest.mark.asyncio
async def test_check_leaderboard_resets_continues_after_guild_failure(db, players):
    """A guild with an invalid timezone doesn't stop other guilds' leaderboard resets."""
    await Guild.upsert(
        db,
        GUILD_ID,
        leaderboard_reset_mode=LeaderboardResetMode.DAILY,
        timezone="Not/AValidZone",
    )
    await Guild.upsert(
        db,
        OTHER_GUILD_ID,
        channel_id=CHANNEL_ID,
        started=1,
        leaderboard_reset_mode=LeaderboardResetMode.DAILY,
    )
    await LeaderboardEntry.upsert(db, OTHER_GUILD_ID, AUTHOR_ID, points=5)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_leaderboard_resets(
        cast(discord.Client, bot), db, datetime(2026, 7, 13, 15, 0)
    )

    assert triggered == 1
    assert await LeaderboardEntry.list(db, guild_id=OTHER_GUILD_ID) == []
