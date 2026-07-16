from datetime import datetime
from pathlib import Path
from typing import cast

import aiosqlite
import discord
import pytest
import pytest_asyncio

from anecbot.features.revealer.service import (
    build_reveal_embed,
    get_due_reveals,
    reveal_anecdote,
    reveal_due_anecdotes,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote
from anecbot.utils.text import with_blank_lines

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2
VOTER_ID = 3


class _FakeMessage:
    """Stand-in for a sent discord.Message — records .edit()/.reply() calls."""

    def __init__(self, message_id: int):
        self.id = message_id
        self.edit_kwargs: dict[str, object] | None = None
        self.reply_embed: discord.Embed | None = None

    async def edit(self, **kwargs: object) -> None:
        """Record exactly which kwargs edit() was called with."""
        self.edit_kwargs = kwargs

    async def reply(self, embed: discord.Embed | None = None) -> "_FakeMessage":
        """Record the embed sent as a reply and return a new fake message."""
        self.reply_embed = embed
        return _FakeMessage(message_id=self.id + 1)


class _FakeChannel:
    """Stand-in for a Messageable channel — pre-seeded with fake messages."""

    def __init__(self, messages: dict[int, _FakeMessage]):
        self._messages = messages
        self.sent_embeds: list[discord.Embed | None] = []

    async def fetch_message(self, message_id: int) -> _FakeMessage:
        """Return the pre-seeded fake message matching the id."""
        return self._messages[message_id]

    async def send(self, *, embed: discord.Embed | None = None) -> _FakeMessage:
        """Record the sent embed (used when the leaderboard is published)."""
        self.sent_embeds.append(embed)
        return _FakeMessage(message_id=len(self.sent_embeds) + 9000)


class _FakeGuild:
    """Stand-in for discord.Guild — only get_member is used (via display_name)."""

    def __init__(self, guild_id: int):
        self.id = guild_id

    def get_member(self, user_id: int) -> None:
        """No cached members in tests — display_name falls back to alias/user id."""
        return None


class _FakeBot:
    """Stand-in for discord.Client — get_channel/get_guild are used by the service."""

    def __init__(
        self, channels: dict[int, _FakeChannel], guild: _FakeGuild | None = None
    ):
        self._channels = channels
        self._guild = guild

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """Return the configured fake guild, or None."""
        return self._guild


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
    """Create a guild (with a configured channel) plus author/target/voter players."""
    await Guild.upsert(
        db, GUILD_ID, channel_id=CHANNEL_ID, reveal_interval_days=1, reveal_time="13:30"
    )
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1, alias="Auteur")
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1, alias="Cible")
    await Player.upsert(db, GUILD_ID, VOTER_ID, can_submit=1, alias="Votant")


async def _published_anecdote(
    db: aiosqlite.Connection, published_at: str, message_id: int = 999
) -> Anecdote:
    """Insert a PUBLISHED anecdote with a fixed published_at and message id."""
    created = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Un truc",
    )
    return await Anecdote.update(
        db,
        created.id,
        state="PUBLISHED",
        published_at=published_at,
        anecdote_message_id=message_id,
    )


@pytest.mark.asyncio
async def test_get_due_reveals_returns_anecdote_past_reveal_time(db, players):
    """An anecdote published on a previous active day, past reveal_time, is due."""
    await _published_anecdote(db, "2026-07-13T15:00:00")  # Monday
    now = datetime(2026, 7, 14, 14, 0)  # Tuesday 14:00, past 13:30 reveal_time

    due = await get_due_reveals(db, GUILD_ID, now)

    assert len(due) == 1


@pytest.mark.asyncio
async def test_get_due_reveals_excludes_not_yet_due(db, players):
    """An anecdote whose reveal time hasn't arrived yet is excluded."""
    await _published_anecdote(db, "2026-07-13T15:00:00")  # Monday
    now = datetime(2026, 7, 14, 10, 0)  # Tuesday 10:00, before 13:30 reveal_time

    due = await get_due_reveals(db, GUILD_ID, now)

    assert due == []


@pytest.mark.asyncio
async def test_get_due_reveals_ignores_non_published(db, players):
    """PENDING anecdotes are never candidates (same for RUNNING/REVEALED)."""
    created = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    now = datetime(2026, 7, 14, 14, 0)

    assert await get_due_reveals(db, GUILD_ID, now) == []
    assert created.state == "PENDING"


@pytest.mark.asyncio
async def test_get_due_reveals_includes_revealing_unconditionally(db, players):
    """A REVEALING anecdote (crashed mid-reveal) is always due, regardless of timing."""
    anecdote = await _published_anecdote(
        db, "2026-07-14T08:00:00"
    )  # not yet due by time
    await Anecdote.update(db, anecdote.id, state="REVEALING")
    now = datetime(2026, 7, 14, 8, 5)  # just after publication, well before reveal_time

    due = await get_due_reveals(db, GUILD_ID, now)

    assert [a.id for a in due] == [anecdote.id]


def test_build_reveal_embed_shows_votes_and_spoiler():
    """The embed lists each vote with a correctness mark and spoiler-tags the answer."""
    anecdote = Anecdote(
        id=1,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        target_id=TARGET_ID,
        content="Un truc drôle",
    )
    votes = [
        Vote(anecdote_id=1, user_id=VOTER_ID, voted_for_id=TARGET_ID),
    ]
    players = {
        AUTHOR_ID: Player(guild_id=GUILD_ID, user_id=AUTHOR_ID, alias="Auteur"),
        TARGET_ID: Player(guild_id=GUILD_ID, user_id=TARGET_ID, alias="Cible"),
        VOTER_ID: Player(guild_id=GUILD_ID, user_id=VOTER_ID, alias="Votant"),
    }

    embed = build_reveal_embed(anecdote, votes, players, None)

    content_field = embed.fields[0]
    assert content_field.value == with_blank_lines("Un truc drôle")
    votes_field = next(f for f in embed.fields if f.name == "🗳️ Votes")
    assert "✅" in (votes_field.value or "")
    assert "Votant" in (votes_field.value or "")
    assert "Cible" in (votes_field.value or "")
    answer_field = next(f for f in embed.fields if f.name == "🎯 Réponse")
    assert answer_field.value == "|| Cible ||"
    author_field = next(f for f in embed.fields if f.name == "✍️ Auteur")
    assert author_field.value == "Auteur"


def test_build_reveal_embed_no_votes():
    """With no votes, the Votes field says so instead of listing anything."""
    anecdote = Anecdote(
        id=1, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )

    embed = build_reveal_embed(anecdote, [], {}, None)

    votes_field = next(f for f in embed.fields if f.name == "🗳️ Votes")
    assert votes_field.value == "Aucun vote."


def test_build_reveal_embed_falls_back_to_count_when_votes_list_too_long():
    """Beyond the field length cap, the per-voter list is replaced by a numeric summary."""
    anecdote = Anecdote(
        id=1, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    players = {
        i: Player(guild_id=GUILD_ID, user_id=i, alias=f"Joueur avec un nom long {i}")
        for i in range(100)
    }
    votes = [
        Vote(anecdote_id=1, user_id=i, voted_for_id=TARGET_ID if i % 2 == 0 else i)
        for i in range(100)
    ]

    embed = build_reveal_embed(anecdote, votes, players, None)

    votes_field = next(f for f in embed.fields if f.name == "🗳️ Votes")
    assert votes_field.value == "✅ 50/100 ont deviné juste"


@pytest.mark.asyncio
async def test_reveal_anecdote_transitions_to_revealed(db, players):
    """Revealing closes the original message's view, replies with the results, and sets REVEALED."""
    anecdote = await _published_anecdote(db, "2026-07-13T15:00:00")
    await Vote.upsert(db, anecdote.id, VOTER_ID, voted_for_id=TARGET_ID)
    message = _FakeMessage(999)
    channel = _FakeChannel({999: message})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    result = await reveal_anecdote(cast(discord.Client, bot), db, anecdote)

    assert result.state == "REVEALED"
    assert message.edit_kwargs == {"view": None}
    assert message.reply_embed is not None
    content_field = message.reply_embed.fields[0]
    assert content_field.value == with_blank_lines("Un truc")

    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "REVEALED"


@pytest.mark.asyncio
async def test_reveal_anecdote_awards_points_to_correct_voter_and_author(db, players):
    """The correct voter and the anecdote's author each get +1 point."""
    anecdote = await _published_anecdote(db, "2026-07-13T15:00:00")
    await Vote.upsert(db, anecdote.id, VOTER_ID, voted_for_id=TARGET_ID)
    channel = _FakeChannel({999: _FakeMessage(999)})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    await reveal_anecdote(cast(discord.Client, bot), db, anecdote)

    voter_entry = await LeaderboardEntry.get(db, GUILD_ID, VOTER_ID)
    assert voter_entry is not None
    assert voter_entry.points == 1
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1


@pytest.mark.asyncio
async def test_reveal_anecdote_no_points_for_wrong_voter(db, players):
    """A voter who guessed wrong gets no point, but the author still does."""
    anecdote = await _published_anecdote(db, "2026-07-13T15:00:00")
    await Vote.upsert(db, anecdote.id, VOTER_ID, voted_for_id=VOTER_ID)
    channel = _FakeChannel({999: _FakeMessage(999)})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    await reveal_anecdote(cast(discord.Client, bot), db, anecdote)

    voter_entry = await LeaderboardEntry.get(db, GUILD_ID, VOTER_ID)
    assert voter_entry is None
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1


@pytest.mark.asyncio
async def test_reveal_anecdote_resumes_from_revealing_without_reawarding(db, players):
    """Resuming a REVEALING anecdote (points already awarded) sends the reply but no extra points."""
    anecdote = await _published_anecdote(db, "2026-07-13T15:00:00")
    await Vote.upsert(db, anecdote.id, VOTER_ID, voted_for_id=TARGET_ID)
    # Simulate a crash right after points were awarded but before the reply was sent.
    await LeaderboardEntry.upsert(db, GUILD_ID, VOTER_ID, points=1)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=1)
    anecdote = await Anecdote.update(db, anecdote.id, state="REVEALING")
    message = _FakeMessage(999)
    channel = _FakeChannel({999: message})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    result = await reveal_anecdote(cast(discord.Client, bot), db, anecdote)

    assert result.state == "REVEALED"
    assert result.reveal_message_id is not None
    assert message.reply_embed is not None
    voter_entry = await LeaderboardEntry.get(db, GUILD_ID, VOTER_ID)
    assert voter_entry is not None
    assert voter_entry.points == 1
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1


@pytest.mark.asyncio
async def test_reveal_anecdote_resumes_from_revealing_with_reply_already_sent(
    db, players
):
    """Resuming a REVEALING anecdote whose reply already went out doesn't send a second one."""
    anecdote = await _published_anecdote(db, "2026-07-13T15:00:00")
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=1)
    anecdote = await Anecdote.update(
        db, anecdote.id, state="REVEALING", reveal_message_id=1000
    )
    message = _FakeMessage(999)
    channel = _FakeChannel({999: message})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    result = await reveal_anecdote(cast(discord.Client, bot), db, anecdote)

    assert result.state == "REVEALED"
    assert message.reply_embed is None
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1


@pytest.mark.asyncio
async def test_reveal_due_anecdotes_reveals_only_due_ones(db, players):
    """Only anecdotes past their reveal time are revealed; others are left PUBLISHED."""
    due = await _published_anecdote(db, "2026-07-13T15:00:00", message_id=999)
    not_due = await _published_anecdote(db, "2026-07-14T09:00:00", message_id=1000)
    channel = _FakeChannel({999: _FakeMessage(999), 1000: _FakeMessage(1000)})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))
    now = datetime(2026, 7, 14, 14, 0)

    revealed = await reveal_due_anecdotes(cast(discord.Client, bot), db, GUILD_ID, now)

    assert [a.id for a in revealed] == [due.id]
    still_published = await Anecdote.get(db, not_due.id)
    assert still_published is not None
    assert still_published.state == "PUBLISHED"


@pytest.mark.asyncio
async def test_reveal_due_anecdotes_publishes_leaderboard_once(db, players):
    """The leaderboard is posted exactly once after the batch, not per anecdote."""
    await _published_anecdote(db, "2026-07-13T15:00:00", message_id=999)
    second = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="Autre"
    )
    await Anecdote.update(
        db,
        second.id,
        state="PUBLISHED",
        published_at="2026-07-13T16:00:00",
        anecdote_message_id=1000,
    )
    channel = _FakeChannel({999: _FakeMessage(999), 1000: _FakeMessage(1000)})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))
    now = datetime(2026, 7, 14, 14, 0)

    revealed = await reveal_due_anecdotes(cast(discord.Client, bot), db, GUILD_ID, now)

    assert len(revealed) == 2
    assert len(channel.sent_embeds) == 1


@pytest.mark.asyncio
async def test_reveal_due_anecdotes_does_not_publish_when_nothing_revealed(db, players):
    """No leaderboard is posted when there's nothing due to reveal."""
    channel = _FakeChannel({})
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))
    now = datetime(2026, 7, 14, 14, 0)

    revealed = await reveal_due_anecdotes(cast(discord.Client, bot), db, GUILD_ID, now)

    assert revealed == []
    assert channel.sent_embeds == []
