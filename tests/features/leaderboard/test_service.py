from datetime import datetime
from typing import cast

import discord
import pytest
import pytest_asyncio

from anecbot.features.anecdote.service import create_anecdote, get_choices
from anecbot.features.leaderboard.service import (
    MAX_LEADERBOARD_ENTRIES,
    award_points,
    build_leaderboard_embed,
    build_player_entries,
    build_ranked_embed,
    get_ranked_entries,
    publish_leaderboard,
    reset_leaderboard,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import AnecdoteState, LeaderboardKind
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote

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

    def __init__(
        self,
        channels: dict[int, _FakeChannel],
        guilds: dict[int, object] | None = None,
    ):
        self._channels = channels
        self._guilds = guilds or {}

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """Return the fake guild registered for the given id, or None."""
        return self._guilds.get(guild_id)


class _FakeMember:
    """Stand-in for discord.Member — only display_name is used."""

    def __init__(self, name: str):
        self.display_name = name


class _FakeGuild:
    """Stand-in for discord.Guild — only get_member is used (via display_name)."""

    def __init__(self, members: dict[int, _FakeMember]):
        self._members = members

    def get_member(self, user_id: int):
        """Return the fake member matching the id, or None."""
        return self._members.get(user_id)


@pytest_asyncio.fixture
async def guild(db):
    """Create the guild row required by the leaderboard table's foreign key."""
    await Guild.upsert(db, GUILD_ID)


@pytest.mark.asyncio
async def test_award_points_credits_correct_voter_and_author_bonus(db, guild):
    """A correct voter gets +1; a wrong voter gets none; the author gets the quality bonus."""
    votes = [
        Vote(anecdote_id=1, user_id=VOTER_ID, voted_for_id=TARGET_ID),
        Vote(anecdote_id=1, user_id=OTHER_VOTER_ID, voted_for_id=OTHER_VOTER_ID),
    ]

    await award_points(db, GUILD_ID, votes, TARGET_ID, AUTHOR_ID, [5])

    voter_entry = await LeaderboardEntry.get(db, GUILD_ID, VOTER_ID)
    assert voter_entry is not None
    assert voter_entry.points == 1
    other_entry = await LeaderboardEntry.get(db, GUILD_ID, OTHER_VOTER_ID)
    assert other_entry is None
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 3


@pytest.mark.asyncio
async def test_award_points_accumulates_across_calls(db, guild):
    """Points accumulate on top of an existing entry rather than overwriting it."""
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    votes = [Vote(anecdote_id=1, user_id=VOTER_ID, voted_for_id=TARGET_ID)]

    await award_points(db, GUILD_ID, votes, TARGET_ID, AUTHOR_ID, [3])

    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 5


@pytest.mark.asyncio
async def test_award_points_author_gets_no_bonus_with_no_quality_votes(db, guild):
    """No quality votes cast means a neutral (0) bonus, not a flat point anymore."""
    await award_points(db, GUILD_ID, [], TARGET_ID, AUTHOR_ID, [])

    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 0


@pytest.mark.asyncio
async def test_award_points_author_gets_malus_for_low_quality(db, guild):
    """A low average quality rating deducts points from the author."""
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)

    await award_points(db, GUILD_ID, [], TARGET_ID, AUTHOR_ID, [1])

    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 3


@pytest.mark.asyncio
async def test_award_points_floors_at_zero(db, guild):
    """A malus larger than the author's current total floors at 0, never goes negative."""
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=1)

    await award_points(db, GUILD_ID, [], TARGET_ID, AUTHOR_ID, [1])

    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 0


def test_build_leaderboard_embed_lists_each_entry():
    """Each entry is shown as its own 'rank. name — value' line in the description."""
    entries = [
        LeaderboardEntry(guild_id=GUILD_ID, user_id=1, points=3),
        LeaderboardEntry(guild_id=GUILD_ID, user_id=2, points=10),
    ]
    players = {
        1: Player(guild_id=GUILD_ID, user_id=1),
        2: Player(guild_id=GUILD_ID, user_id=2),
    }
    guild = _FakeGuild({1: _FakeMember("Alice"), 2: _FakeMember("Bob")})

    embed = build_leaderboard_embed(entries, players, cast(discord.Guild, guild))

    assert embed.title == "🏆 Classement"
    assert embed.description == "1. Bob — 10 pt(s)\n2. Alice — 3 pt(s)"


def test_build_leaderboard_embed_caps_to_top_n():
    """Beyond MAX_LEADERBOARD_ENTRIES, a trailing count note is appended to the description."""
    entries = [
        LeaderboardEntry(guild_id=GUILD_ID, user_id=i, points=i)
        for i in range(MAX_LEADERBOARD_ENTRIES + 5)
    ]

    embed = build_leaderboard_embed(entries, {}, None)

    assert embed.description is not None
    assert embed.description.endswith("\n... et 5 joueur(s) de plus")
    assert len(embed.description.splitlines()) == MAX_LEADERBOARD_ENTRIES + 1


def test_build_leaderboard_embed_empty():
    """With no entries, a placeholder message is shown instead of an empty list."""
    embed = build_leaderboard_embed([], {}, None)

    assert embed.description == "Aucun point pour l'instant."


@pytest.mark.asyncio
async def test_publish_leaderboard_sends_embed(db):
    """The leaderboard embed is sent to the guild's configured channel."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID)
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


@pytest.mark.asyncio
async def test_reset_leaderboard_clears_entries_and_stamps_time(db, guild):
    """All points for the guild are wiped and last_leaderboard_reset_at is recorded."""
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    await LeaderboardEntry.upsert(db, GUILD_ID, VOTER_ID, points=2)
    now = datetime(2026, 7, 13, 15, 0)

    await reset_leaderboard(db, GUILD_ID, now)

    assert await LeaderboardEntry.list(db, guild_id=GUILD_ID) == []
    updated = await Guild.get(db, GUILD_ID)
    assert updated is not None
    assert updated.last_leaderboard_reset_at == now.isoformat()


@pytest.mark.asyncio
async def test_reset_leaderboard_does_not_touch_other_guilds(db, guild):
    """Only the target guild's entries are cleared."""
    other_guild_id = GUILD_ID + 1
    await Guild.upsert(db, other_guild_id)
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=5)
    await LeaderboardEntry.upsert(db, other_guild_id, AUTHOR_ID, points=3)

    await reset_leaderboard(db, GUILD_ID, datetime(2026, 7, 13, 15, 0))

    assert await LeaderboardEntry.list(db, guild_id=GUILD_ID) == []
    other_entry = await LeaderboardEntry.get(db, other_guild_id, AUTHOR_ID)
    assert other_entry is not None
    assert other_entry.points == 3


def test_build_ranked_embed_uses_custom_empty_message():
    """A caller-provided empty_message is shown instead of the points-specific default."""
    embed = build_ranked_embed("Titre", [], "Rien pour l'instant.", {}, None)

    assert embed.title == "Titre"
    assert embed.description == "Rien pour l'instant."


def test_build_player_entries_caps_and_labels_with_rank_and_value():
    """Entries are capped to MAX_LEADERBOARD_ENTRIES and labeled 'rank. name — value'."""
    rows = [(i, f"{i} pt(s)") for i in range(MAX_LEADERBOARD_ENTRIES + 5)]
    players = {i: Player(guild_id=GUILD_ID, user_id=i) for i, _ in rows}
    guild = _FakeGuild({i: _FakeMember(f"Joueur{i}") for i, _ in rows})

    entries = build_player_entries(rows, players, cast(discord.Guild, guild))

    assert len(entries) == MAX_LEADERBOARD_ENTRIES
    assert entries[0] == (0, "1. Joueur0 — 0 pt(s)")
    assert entries[1] == (1, "2. Joueur1 — 1 pt(s)")


@pytest_asyncio.fixture
async def two_anecdotes(db):
    """Two anecdotes by AUTHOR_ID, each with a correct and a wrong choice."""
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
    return anecdote, other_anecdote, choices, other_choices


@pytest.mark.asyncio
async def test_get_ranked_entries_points(db, guild):
    """POINTS ranks by leaderboard points, formatted as 'X pt(s)'."""
    await LeaderboardEntry.upsert(db, GUILD_ID, AUTHOR_ID, points=3)
    await LeaderboardEntry.upsert(db, GUILD_ID, VOTER_ID, points=10)

    rows = await get_ranked_entries(db, GUILD_ID, LeaderboardKind.POINTS)

    assert rows == [(VOTER_ID, "10 pt(s)"), (AUTHOR_ID, "3 pt(s)")]


@pytest.mark.asyncio
async def test_get_ranked_entries_votes(db, two_anecdotes):
    """VOTES ranks by votes cast, formatted as 'X vote(s)'."""
    anecdote, other_anecdote, choices, other_choices = two_anecdotes
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

    rows = await get_ranked_entries(db, GUILD_ID, LeaderboardKind.VOTES)

    assert rows == [(VOTER_ID, "2 vote(s)"), (OTHER_VOTER_ID, "1 vote(s)")]


@pytest.mark.asyncio
async def test_get_ranked_entries_published_only_counts_revealed(db, two_anecdotes):
    """PUBLISHED ranks by REVEALED anecdotes only."""
    anecdote, other_anecdote, _, _ = two_anecdotes
    await Anecdote.update(db, anecdote.id, state=AnecdoteState.REVEALED)
    await Anecdote.update(db, other_anecdote.id, state=AnecdoteState.PUBLISHED)

    rows = await get_ranked_entries(db, GUILD_ID, LeaderboardKind.PUBLISHED)

    assert rows == [(AUTHOR_ID, "1 anecdote(s)")]


@pytest.mark.asyncio
async def test_get_ranked_entries_accuracy_excludes_zero_votes(db, two_anecdotes):
    """ACCURACY only ranks players who cast at least one vote."""
    anecdote, other_anecdote, choices, other_choices = two_anecdotes
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

    rows = await get_ranked_entries(db, GUILD_ID, LeaderboardKind.ACCURACY)

    assert rows == [(VOTER_ID, "1/2 (50%)")]
