from typing import cast

import discord
import pytest
import pytest_asyncio

from anecbot.features.anecdote.service import (
    backfill_migrated_target_labels,
    create_anecdote,
    daily_limit_status,
    delete_anecdote,
    discard_pending_anecdotes,
    get_choices,
    get_correct_choice,
    get_owned_pending_anecdote,
    get_pending_by_author,
    player_has_anecdotes,
    update_content,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.anecdote_choice import AnecdoteChoice
from anecbot.models.guild import Guild
from anecbot.models.player import Player

GUILD_ID = 100
AUTHOR_ID = 1
TARGET_ID = 2


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
        await Anecdote.create(db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x")

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 0)


@pytest.mark.asyncio
async def test_daily_limit_status_under_limit(db, players):
    """Returns (False, limit) while the author is still under the configured limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=2)
    await Anecdote.create(db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x")

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 2)


@pytest.mark.asyncio
async def test_daily_limit_status_at_limit(db, players):
    """Returns (True, limit) once the author has reached the configured limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=2)
    for _ in range(2):
        await Anecdote.create(db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x")

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (True, 2)


@pytest.mark.asyncio
async def test_daily_limit_status_ignores_other_authors(db, players):
    """Only the given author's submissions count toward their own limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=1)
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    await Anecdote.create(db, guild_id=GUILD_ID, author_id=3, content="x")

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 1)


@pytest.mark.asyncio
async def test_daily_limit_status_ignores_past_days(db, players):
    """Anecdotes created on a previous day don't count toward today's limit."""
    await Guild.upsert(db, GUILD_ID, daily_limit=1)
    await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        content="x",
        created_at="2020-01-01T00:00:00",
    )

    assert await daily_limit_status(db, GUILD_ID, AUTHOR_ID) == (False, 1)


@pytest.mark.asyncio
async def test_create_anecdote_defaults_to_pending(db, players):
    """create_anecdote saves the anecdote with state PENDING."""
    result = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "Un truc drôle",
        target_label="Cible",
        choice_labels=["Autre"],
    )

    assert result.state == "PENDING"
    assert result.guild_id == GUILD_ID
    assert result.author_id == AUTHOR_ID
    assert result.content == "Un truc drôle"


@pytest.mark.asyncio
async def test_create_anecdote_writes_choices(db, players):
    """create_anecdote writes one correct choice (the target) plus the wrong choices."""
    anecdote = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "x",
        target_label="Le stagiaire",
        choice_labels=["Le concierge", "Le DRH"],
    )

    choices = await get_choices(db, anecdote.id)
    assert len(choices) == 3
    labels = {c.label for c in choices}
    assert labels == {"Le stagiaire", "Le concierge", "Le DRH"}
    correct = [c for c in choices if c.is_correct]
    assert len(correct) == 1
    assert correct[0].label == "Le stagiaire"


@pytest.mark.asyncio
async def test_create_anecdote_with_no_wrong_choices(db, players):
    """create_anecdote works with only the correct choice and no wrong ones."""
    anecdote = await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "x", target_label="Le stagiaire", choice_labels=[]
    )

    choices = await get_choices(db, anecdote.id)
    assert len(choices) == 1
    assert choices[0].label == "Le stagiaire"
    assert choices[0].is_correct == 1


@pytest.mark.asyncio
async def test_create_anecdote_clears_empty_queue_warning(db, players):
    """create_anecdote resets the guild's queue_empty_warned flag."""
    await Guild.upsert(db, GUILD_ID, queue_empty_warned=1)

    await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, "x", target_label="Cible", choice_labels=[]
    )

    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None
    assert guild.queue_empty_warned == 0


@pytest.mark.asyncio
async def test_get_correct_choice_returns_the_target(db, players):
    """get_correct_choice returns the choice flagged as correct, not a wrong one."""
    anecdote = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "x",
        target_label="Le stagiaire",
        choice_labels=["Le concierge"],
    )

    correct = await get_correct_choice(db, anecdote.id)
    assert correct.label == "Le stagiaire"
    assert correct.is_correct == 1


@pytest.mark.asyncio
async def test_get_pending_by_author_only_pending(db, players):
    """Only PENDING anecdotes are returned, not published/revealed ones."""
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="P"
    )
    published = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Q"
    )
    await Anecdote.update(db, published.id, state="PUBLISHED")

    result = await get_pending_by_author(db, GUILD_ID, AUTHOR_ID)
    assert [a.id for a in result] == [pending.id]


@pytest.mark.asyncio
async def test_get_pending_by_author_only_own(db, players):
    """Only the given author's anecdotes are returned, not other authors'."""
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    mine = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Mine"
    )
    await Anecdote.create(db, guild_id=GUILD_ID, author_id=3, content="Theirs")

    result = await get_pending_by_author(db, GUILD_ID, AUTHOR_ID)
    assert [a.id for a in result] == [mine.id]


@pytest.mark.asyncio
async def test_get_pending_by_author_sorted_most_recent_first(db, players):
    """Anecdotes are returned newest first, by created_at then id as tiebreaker."""
    oldest = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        content="Oldest",
        created_at="2026-01-01T10:00:00",
    )
    newest = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        content="Newest",
        created_at="2026-01-03T10:00:00",
    )
    middle = await Anecdote.create(
        db,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        content="Middle",
        created_at="2026-01-02T10:00:00",
    )

    result = await get_pending_by_author(db, GUILD_ID, AUTHOR_ID)
    assert [a.id for a in result] == [newest.id, middle.id, oldest.id]


@pytest.mark.asyncio
async def test_update_content_changes_text(db, players):
    """update_content overwrites the anecdote's content."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Old"
    )

    result = await update_content(db, anecdote.id, "New")
    assert result.content == "New"
    assert result.state == "PENDING"


@pytest.mark.asyncio
async def test_delete_anecdote_removes_row(db, players):
    """delete_anecdote removes the row and returns True."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Bye"
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
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Mine"
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
        db, guild_id=GUILD_ID, author_id=3, content="Theirs"
    )

    assert await get_owned_pending_anecdote(db, anecdote.id, AUTHOR_ID) is None


@pytest.mark.asyncio
async def test_get_owned_pending_anecdote_none_when_not_pending(db, players):
    """Returns None once the anecdote is no longer PENDING (e.g. published)."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Mine"
    )
    await Anecdote.update(db, anecdote.id, state="PUBLISHED")

    assert await get_owned_pending_anecdote(db, anecdote.id, AUTHOR_ID) is None


@pytest.mark.asyncio
async def test_player_has_anecdotes_false_when_none(db, players):
    """Returns False when the user hasn't authored any anecdote."""
    assert await player_has_anecdotes(db, GUILD_ID, AUTHOR_ID) is False


@pytest.mark.asyncio
async def test_player_has_anecdotes_true_as_author(db, players):
    """Returns True when the user authored an anecdote, regardless of its state."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="REVEALED")

    assert await player_has_anecdotes(db, GUILD_ID, AUTHOR_ID) is True


@pytest.mark.asyncio
async def test_player_has_anecdotes_ignores_other_guilds(db, players):
    """Only counts anecdotes in the given guild."""
    other_guild = 200
    await Guild.upsert(db, other_guild)
    await Player.upsert(db, other_guild, AUTHOR_ID, can_submit=1)
    await Anecdote.create(db, guild_id=other_guild, author_id=AUTHOR_ID, content="x")

    assert await player_has_anecdotes(db, GUILD_ID, AUTHOR_ID) is False


@pytest.mark.asyncio
async def test_discard_pending_anecdotes_removes_only_pending(db, players):
    """Only the author's PENDING anecdotes are deleted, published/revealed ones are kept."""
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="P"
    )
    published = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="Q"
    )
    await Anecdote.update(db, published.id, state="PUBLISHED")

    count = await discard_pending_anecdotes(db, GUILD_ID, AUTHOR_ID)

    assert count == 1
    assert await Anecdote.get(db, pending.id) is None
    assert await Anecdote.get(db, published.id) is not None


@pytest.mark.asyncio
async def test_discard_pending_anecdotes_ignores_other_authors(db, players):
    """Anecdotes authored by someone else are left untouched."""
    await Player.upsert(db, GUILD_ID, 3, can_submit=1)
    anecdote = await Anecdote.create(db, guild_id=GUILD_ID, author_id=3, content="x")

    count = await discard_pending_anecdotes(db, GUILD_ID, AUTHOR_ID)

    assert count == 0
    assert await Anecdote.get(db, anecdote.id) is not None


@pytest.mark.asyncio
async def test_discard_pending_anecdotes_returns_zero_when_none(db, players):
    """Returns 0 when the author has no PENDING anecdotes."""
    assert await discard_pending_anecdotes(db, GUILD_ID, AUTHOR_ID) == 0


# --- backfill_migrated_target_labels ---


class _FakeMember:
    """Stand-in for discord.Member — only display_name is used."""

    def __init__(self, name: str):
        self.display_name = name


class _FakeGuild:
    """Stand-in for discord.Guild — only get_member is used."""

    def __init__(self, members: dict[int, _FakeMember] | None = None):
        self._members = members or {}

    def get_member(self, user_id: int) -> "_FakeMember | None":
        """Return the fake member matching the id, or None."""
        return self._members.get(user_id)


class _FakeBot:
    """Stand-in for discord.Client — only get_guild is used."""

    def __init__(self, guild: "_FakeGuild | None"):
        self._guild = guild

    def get_guild(self, guild_id: int):
        """Return the configured fake guild, or None."""
        return self._guild


@pytest.mark.asyncio
async def test_backfill_resolves_numeric_labels_to_display_names(db, players):
    """A purely-numeric label matching a cached member is replaced by their display name."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    choice = await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label=str(TARGET_ID), is_correct=1
    )
    bot = _FakeBot(_FakeGuild({TARGET_ID: _FakeMember("Cible")}))

    resolved = await backfill_migrated_target_labels(cast(discord.Client, bot), db)

    assert resolved == 1
    updated = await AnecdoteChoice.get(db, choice.id)
    assert updated is not None
    assert updated.label == "Cible"


@pytest.mark.asyncio
async def test_backfill_skips_unresolvable_numeric_labels(db, players):
    """A numeric label with no matching cached member is left untouched."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    choice = await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label=str(TARGET_ID), is_correct=1
    )
    bot = _FakeBot(_FakeGuild({}))

    resolved = await backfill_migrated_target_labels(cast(discord.Client, bot), db)

    assert resolved == 0
    updated = await AnecdoteChoice.get(db, choice.id)
    assert updated is not None
    assert updated.label == str(TARGET_ID)


@pytest.mark.asyncio
async def test_backfill_ignores_non_numeric_labels(db, players):
    """A regular free-text label (custom target or already-resolved name) is left untouched."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    choice = await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label="Le stagiaire", is_correct=1
    )
    bot = _FakeBot(_FakeGuild({TARGET_ID: _FakeMember("Cible")}))

    resolved = await backfill_migrated_target_labels(cast(discord.Client, bot), db)

    assert resolved == 0
    updated = await AnecdoteChoice.get(db, choice.id)
    assert updated is not None
    assert updated.label == "Le stagiaire"


@pytest.mark.asyncio
async def test_backfill_ignores_revealed_anecdotes(db, players):
    """REVEALED anecdotes are left alone — their choices are historical, not upcoming UI."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="REVEALED")
    choice = await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label=str(TARGET_ID), is_correct=1
    )
    bot = _FakeBot(_FakeGuild({TARGET_ID: _FakeMember("Cible")}))

    resolved = await backfill_migrated_target_labels(cast(discord.Client, bot), db)

    assert resolved == 0
    updated = await AnecdoteChoice.get(db, choice.id)
    assert updated is not None
    assert updated.label == str(TARGET_ID)


@pytest.mark.asyncio
async def test_backfill_skips_guild_bot_has_left(db, players):
    """No lookup is attempted for a guild the bot is no longer in."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    choice = await AnecdoteChoice.create(
        db, anecdote_id=anecdote.id, label=str(TARGET_ID), is_correct=1
    )
    bot = _FakeBot(None)

    resolved = await backfill_migrated_target_labels(cast(discord.Client, bot), db)

    assert resolved == 0
    updated = await AnecdoteChoice.get(db, choice.id)
    assert updated is not None
    assert updated.label == str(TARGET_ID)
