from pathlib import Path
from typing import cast

import aiosqlite
import discord
import pytest
import pytest_asyncio

from anecbot.features.leaderboard.service import (
    MAX_LEADERBOARD_ENTRIES,
    award_points,
    build_leaderboard_embed,
    publish_leaderboard,
)
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2
VOTER_ID = 3
OTHER_VOTER_ID = 4


class _FakeMessage:
    """Stand-in for a sent discord.Message — only .id is used here."""

    def __init__(self, message_id: int):
        self.id = message_id


class _FakeChannel:
    """Stand-in for a Messageable channel — records sent embeds."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed | None] = []

    async def send(self, *, embed: discord.Embed | None = None) -> _FakeMessage:
        """Record the sent embed."""
        self.sent_embeds.append(embed)
        return _FakeMessage(message_id=999)


class _FakeBot:
    """Stand-in for discord.Client — get_channel/get_guild are used by the service."""

    def __init__(self, channels: dict[int, _FakeChannel]):
        self._channels = channels

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """No fake discord.Guild needed for these tests."""
        return None


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest_asyncio.fixture
async def guild(db):
    """Create the guild row required by the leaderboard table's foreign key."""
    await Guild.upsert(db, GUILD_ID)


@pytest.mark.asyncio
async def test_award_points_credits_correct_voter_and_author(db, guild):
    """A correct voter and the author each get +1 point; a wrong voter gets none."""
    votes = [
        Vote(anecdote_id=1, user_id=VOTER_ID, voted_for_id=TARGET_ID),
        Vote(anecdote_id=1, user_id=OTHER_VOTER_ID, voted_for_id=OTHER_VOTER_ID),
    ]

    await award_points(db, GUILD_ID, votes, TARGET_ID, AUTHOR_ID)

    voter_entry = await LeaderboardEntry.get(db, GUILD_ID, VOTER_ID)
    assert voter_entry is not None
    assert voter_entry.points == 1
    other_entry = await LeaderboardEntry.get(db, GUILD_ID, OTHER_VOTER_ID)
    assert other_entry is None
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1


@pytest.mark.asyncio
async def test_award_points_accumulates_across_calls(db, guild):
    """Points accumulate on top of an existing entry rather than overwriting it."""
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    votes = [Vote(anecdote_id=1, user_id=VOTER_ID, voted_for_id=TARGET_ID)]

    await award_points(db, GUILD_ID, votes, TARGET_ID, AUTHOR_ID)

    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 6


@pytest.mark.asyncio
async def test_award_points_author_gets_point_even_with_no_votes(db, guild):
    """The author's flat point isn't dependent on anyone voting at all."""
    await award_points(db, GUILD_ID, [], TARGET_ID, AUTHOR_ID)

    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1


def test_build_leaderboard_embed_ranks_by_points_descending():
    """Entries are shown ranked from highest to lowest points."""
    entries = [
        LeaderboardEntry(guild_id=GUILD_ID, user_id=1, points=3),
        LeaderboardEntry(guild_id=GUILD_ID, user_id=2, points=10),
    ]
    players = {
        1: Player(guild_id=GUILD_ID, user_id=1, alias="Alice"),
        2: Player(guild_id=GUILD_ID, user_id=2, alias="Bob"),
    }

    embed = build_leaderboard_embed(entries, players, None)

    assert embed.description is not None
    lines = embed.description.split("\n")
    assert lines[0].startswith("**1.** Bob")
    assert lines[1].startswith("**2.** Alice")


def test_build_leaderboard_embed_caps_to_top_n():
    """Beyond MAX_LEADERBOARD_ENTRIES, a trailing count note is shown instead of more rows."""
    entries = [
        LeaderboardEntry(guild_id=GUILD_ID, user_id=i, points=i)
        for i in range(MAX_LEADERBOARD_ENTRIES + 5)
    ]
    players = {
        i: Player(guild_id=GUILD_ID, user_id=i, alias=f"Joueur{i}")
        for i in range(MAX_LEADERBOARD_ENTRIES + 5)
    }

    embed = build_leaderboard_embed(entries, players, None)

    assert embed.description is not None
    lines = embed.description.split("\n")
    assert len(lines) == MAX_LEADERBOARD_ENTRIES + 1
    assert lines[-1] == "... et 5 joueur(s) de plus"


def test_build_leaderboard_embed_empty():
    """With no entries, a placeholder message is shown instead of an empty list."""
    embed = build_leaderboard_embed([], {}, None)

    assert embed.description == "Aucun point pour l'instant."


@pytest.mark.asyncio
async def test_publish_leaderboard_sends_embed(db):
    """The leaderboard embed is sent to the guild's configured channel."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, alias="Auteur")
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=3)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    await publish_leaderboard(cast(discord.Client, bot), db, GUILD_ID)

    assert len(channel.sent_embeds) == 1
    assert channel.sent_embeds[0] is not None


@pytest.mark.asyncio
async def test_publish_leaderboard_skips_when_no_entries(db):
    """Nothing is sent when the leaderboard is empty."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    await publish_leaderboard(cast(discord.Client, bot), db, GUILD_ID)

    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_publish_leaderboard_skips_when_no_channel_configured(db):
    """Nothing is sent when the guild has no channel configured."""
    await Guild.upsert(db, GUILD_ID)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=3)
    bot = _FakeBot({})

    await publish_leaderboard(cast(discord.Client, bot), db, GUILD_ID)
