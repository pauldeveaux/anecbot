from datetime import datetime
from typing import cast

import discord
import pytest
import pytest_asyncio

from anecbot.features.anecdote.service import create_anecdote
from anecbot.features.publisher.service import (
    build_anecdote_embed,
    build_mcq_options,
    publish_and_open_voting,
    publish_next_anecdote,
    recover_stuck_publications,
    refresh_published_reveal_dates,
    restore_active_views,
    send_empty_queue_warning,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.anecdote_media import AnecdoteMedia
from anecbot.models.guild import Guild
from anecbot.models.player import Player
from anecbot.utils.text import with_blank_lines

GUILD_ID = 100
CHANNEL_ID = 555
AUTHOR_ID = 1
TARGET_ID = 2


class _FakeMessage:
    """Stand-in for a sent discord.Message — .id is read, .edit() calls are recorded."""

    def __init__(self, message_id: int):
        self.id = message_id
        self.edit_kwargs: dict[str, object] | None = None

    async def edit(self, **kwargs: object) -> None:
        """Record exactly which kwargs edit() was called with."""
        self.edit_kwargs = kwargs


class _FakeChannel:
    """Stand-in for a Messageable channel — records sends, returns fake messages."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed | None] = []
        self.sent_embed_lists: list[list[discord.Embed]] = []
        self.sent_contents: list[str | None] = []
        self._messages: dict[int, _FakeMessage] = {}

    async def send(
        self, content: str | None = None, *, embeds: list[discord.Embed] | None = None
    ) -> _FakeMessage:
        """Record the send and return a fake message with a fixed id."""
        self.sent_embed_lists.append(list(embeds or []))
        self.sent_embeds.append(embeds[0] if embeds else None)
        self.sent_contents.append(content)
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
    """Stand-in for discord.Client — get_channel/get_guild/add_view are used by the service."""

    def __init__(
        self, channels: dict[int, _FakeChannel], guild: _FakeGuild | None = None
    ):
        self._channels = channels
        self._guild = guild
        self.added_views: list[tuple[discord.ui.View, int | None]] = []

    def get_channel(self, channel_id: int):
        """Return the fake channel for the given id, or None."""
        return self._channels.get(channel_id)

    def get_guild(self, guild_id: int):
        """Return the configured fake guild, or None."""
        return self._guild

    def add_view(self, view: discord.ui.View, *, message_id: int | None = None):
        """Record the view/message_id pair a persistent-view registration was called with."""
        self.added_views.append((view, message_id))


@pytest_asyncio.fixture
async def players(db):
    """Create a guild (with a configured channel) plus an author and a target player."""
    await Guild.upsert(db, GUILD_ID, channel_id=CHANNEL_ID)
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)


async def _create_anecdote(db, content: str = "x") -> Anecdote:
    """Create an anecdote with its MCQ choices via the real service, ready to publish/reveal."""
    return await create_anecdote(
        db, GUILD_ID, AUTHOR_ID, content, target_label="Cible", choice_labels=["Autre"]
    )


def test_build_anecdote_embed_shows_content_only():
    """With no media, a single embed is returned, holding the content and no reveal date."""
    anecdote = Anecdote(
        id=1,
        guild_id=GUILD_ID,
        author_id=AUTHOR_ID,
        content="Un truc drôle",
    )

    embeds = build_anecdote_embed(anecdote)

    assert len(embeds) == 1
    content_field = embeds[0].fields[0]
    assert content_field.value == with_blank_lines("Un truc drôle")
    assert str(AUTHOR_ID) not in (embeds[0].title or "")
    assert all(f.name != "🔍 Révélation prévue" for f in embeds[0].fields)
    assert embeds[0].image.url is None


def test_build_anecdote_embed_shows_reveal_date_when_given():
    """When a reveal_at datetime is passed, it's shown as a dedicated field on a second embed.

    A separate trailing embed (not a field on the main one) so a set image on the main embed —
    which Discord always renders below all of that embed's own fields — still ends up above the
    reveal date rather than below it.
    """
    anecdote = Anecdote(id=1, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x")
    reveal_at = datetime(2026, 7, 15, 13, 30)

    embeds = build_anecdote_embed(anecdote, reveal_at=reveal_at)

    assert len(embeds) == 2
    reveal_field = next(f for f in embeds[1].fields if f.name == "🔍 Révélation prévue")
    assert reveal_field.value is not None
    assert all(f.name != "🔍 Révélation prévue" for f in embeds[0].fields)


def test_build_anecdote_embed_sets_main_image():
    """A given image url is set as the main embed's image."""
    anecdote = Anecdote(id=1, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x")

    embeds = build_anecdote_embed(anecdote, "https://example.com/a.gif")

    assert len(embeds) == 1
    assert embeds[0].image.url == "https://example.com/a.gif"


@pytest.mark.asyncio
async def test_publish_next_anecdote_transitions_to_running(db, players):
    """Publishing sends the embed, sets state to RUNNING, and stores the message id."""
    anecdote = await _create_anecdote(db)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    result = await publish_next_anecdote(cast(discord.Client, bot), db, GUILD_ID)

    assert result is not None
    assert result.state == "RUNNING"
    assert result.anecdote_message_id == 999
    assert len(channel.sent_embeds) == 1
    sent_embed = channel.sent_embeds[0]
    assert sent_embed is not None
    content_field = sent_embed.fields[0]
    assert content_field.value == with_blank_lines("x")

    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "RUNNING"
    assert stored.anecdote_message_id == 999


@pytest.mark.asyncio
async def test_publish_next_anecdote_sets_media_as_embed_image(db, players):
    """A stored media url is set as the embed's image."""
    await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "x",
        target_label="Cible",
        choice_labels=["Autre"],
        media=[AnecdoteMedia(media_url="https://example.com/a.png")],
    )
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    await publish_next_anecdote(cast(discord.Client, bot), db, GUILD_ID)

    assert channel.sent_embed_lists[0][0].image.url == "https://example.com/a.png"


@pytest.mark.asyncio
async def test_publish_next_anecdote_returns_none_when_queue_empty(db, players):
    """Returns None and sends nothing when there's no PENDING anecdote."""
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    result = await publish_next_anecdote(cast(discord.Client, bot), db, GUILD_ID)

    assert result is None
    assert channel.sent_embeds == []


@pytest.mark.asyncio
async def test_send_empty_queue_warning_sends_once(db, players):
    """The warning is sent and the flag is set when not already warned."""
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    await send_empty_queue_warning(cast(discord.Client, bot), db, guild)

    assert len(channel.sent_contents) == 1
    updated = await Guild.get(db, GUILD_ID)
    assert updated is not None
    assert updated.queue_empty_warned == 1


@pytest.mark.asyncio
async def test_send_empty_queue_warning_skips_when_already_warned(db, players):
    """No duplicate warning is sent once the flag is already set."""
    await Guild.upsert(db, GUILD_ID, queue_empty_warned=1)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})
    guild = await Guild.get(db, GUILD_ID)
    assert guild is not None

    await send_empty_queue_warning(cast(discord.Client, bot), db, guild)

    assert channel.sent_contents == []


@pytest.mark.asyncio
async def test_publish_and_open_voting_reaches_published(db, players):
    """Publishing attaches the MCQ, shows the reveal date, and sets published_at."""
    await _create_anecdote(db)
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    result = await publish_and_open_voting(cast(discord.Client, bot), db, GUILD_ID)

    assert result is not None
    assert result.state == "PUBLISHED"
    assert result.published_at is not None

    sent_message = channel._messages[999]
    assert sent_message.edit_kwargs is not None
    assert isinstance(sent_message.edit_kwargs["view"], discord.ui.View)
    published_embeds = sent_message.edit_kwargs["embeds"]
    assert isinstance(published_embeds, list)
    assert any(
        f.name == "🔍 Révélation prévue"
        for embed in published_embeds
        for f in embed.fields
    )


@pytest.mark.asyncio
async def test_publish_and_open_voting_warns_once_when_empty(db, players):
    """An empty queue triggers the warning once, not on a second call."""
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    first = await publish_and_open_voting(cast(discord.Client, bot), db, GUILD_ID)
    second = await publish_and_open_voting(cast(discord.Client, bot), db, GUILD_ID)

    assert first is None
    assert second is None
    assert len(channel.sent_contents) == 1


@pytest.mark.asyncio
async def test_refresh_published_reveal_dates_updates_message(db, players):
    """Every PUBLISHED anecdote's message is re-edited with a fresh reveal date."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    await Anecdote.update(
        db,
        anecdote.id,
        state="PUBLISHED",
        published_at="2026-07-13T15:00:00",
        anecdote_message_id=999,
    )
    channel = _FakeChannel()
    channel._messages[999] = _FakeMessage(999)
    bot = _FakeBot({CHANNEL_ID: channel})

    await refresh_published_reveal_dates(cast(discord.Client, bot), db, GUILD_ID)

    message = channel._messages[999]
    assert message.edit_kwargs is not None
    updated_embeds = message.edit_kwargs["embeds"]
    assert isinstance(updated_embeds, list)
    assert any(
        f.name == "🔍 Révélation prévue"
        for embed in updated_embeds
        for f in embed.fields
    )
    assert "view" not in message.edit_kwargs


@pytest.mark.asyncio
async def test_refresh_published_reveal_dates_ignores_non_published(db, players):
    """PENDING/RUNNING/REVEALED anecdotes' messages are left untouched."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="RUNNING", anecdote_message_id=999)
    channel = _FakeChannel()
    channel._messages[999] = _FakeMessage(999)
    bot = _FakeBot({CHANNEL_ID: channel})

    await refresh_published_reveal_dates(cast(discord.Client, bot), db, GUILD_ID)

    assert channel._messages[999].edit_kwargs is None


@pytest.mark.asyncio
async def test_refresh_published_reveal_dates_no_channel_configured(db):
    """No-op when the guild has no channel configured (nothing to crash on)."""
    await Guild.upsert(db, GUILD_ID)
    bot = _FakeBot({})

    await refresh_published_reveal_dates(cast(discord.Client, bot), db, GUILD_ID)


# --- build_mcq_options ---


@pytest.mark.asyncio
async def test_build_mcq_options_uses_anecdote_choices(db, players):
    """Options are built from the anecdote's own choices, target included."""
    anecdote = await create_anecdote(
        db,
        GUILD_ID,
        AUTHOR_ID,
        "x",
        target_label="Le stagiaire",
        choice_labels=["Le concierge", "Le DRH"],
    )

    options = await build_mcq_options(db, anecdote)

    labels = {label for label, _ in options}
    assert labels == {"Le stagiaire", "Le concierge", "Le DRH"}
    assert len(options) == 3


# --- recover_stuck_publications ---


@pytest.mark.asyncio
async def test_recover_stuck_publications_finishes_when_message_was_sent(db, players):
    """A RUNNING anecdote with a known message id resumes to PUBLISHED with the MCQ view."""
    anecdote = await _create_anecdote(db)
    await Anecdote.update(db, anecdote.id, state="RUNNING", anecdote_message_id=999)
    channel = _FakeChannel()
    channel._messages[999] = _FakeMessage(999)
    bot = _FakeBot({CHANNEL_ID: channel}, guild=_FakeGuild(GUILD_ID))

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 1
    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "PUBLISHED"
    assert stored.published_at is not None
    edit_kwargs = channel._messages[999].edit_kwargs
    assert edit_kwargs is not None
    assert isinstance(edit_kwargs["view"], discord.ui.View)


@pytest.mark.asyncio
async def test_recover_stuck_publications_reverts_when_message_was_never_sent(
    db, players
):
    """A RUNNING anecdote with no known message id reverts to PENDING for a clean retry."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="RUNNING")
    bot = _FakeBot({}, guild=_FakeGuild(GUILD_ID))

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 1
    stored = await Anecdote.get(db, anecdote.id)
    assert stored is not None
    assert stored.state == "PENDING"


@pytest.mark.asyncio
async def test_recover_stuck_publications_ignores_other_states(db, players):
    """PENDING/PUBLISHED/REVEALED anecdotes are left untouched."""
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    bot = _FakeBot({}, guild=_FakeGuild(GUILD_ID))

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 0
    stored = await Anecdote.get(db, pending.id)
    assert stored is not None
    assert stored.state == "PENDING"


@pytest.mark.asyncio
async def test_recover_stuck_publications_no_channel_configured(db):
    """No-op when the guild has no channel configured."""
    await Guild.upsert(db, GUILD_ID)
    bot = _FakeBot({})

    count = await recover_stuck_publications(cast(discord.Client, bot), db, GUILD_ID)

    assert count == 0


# --- restore_active_views ---


@pytest.mark.asyncio
async def test_restore_active_views_registers_a_view_per_published_anecdote(
    db, players
):
    """Each PUBLISHED anecdote gets a persistent view registered, bound to its message id."""
    anecdote = await _create_anecdote(db)
    await Anecdote.update(db, anecdote.id, state="PUBLISHED", anecdote_message_id=999)
    bot = _FakeBot({}, guild=_FakeGuild(GUILD_ID))

    await restore_active_views(cast(discord.Client, bot), db)

    assert len(bot.added_views) == 1
    view, message_id = bot.added_views[0]
    assert isinstance(view, discord.ui.View)
    assert message_id == 999


@pytest.mark.asyncio
async def test_restore_active_views_ignores_other_states(db, players):
    """PENDING/RUNNING/REVEALED anecdotes get no view registered."""
    await Anecdote.create(db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x")
    bot = _FakeBot({}, guild=_FakeGuild(GUILD_ID))

    await restore_active_views(cast(discord.Client, bot), db)

    assert bot.added_views == []


@pytest.mark.asyncio
async def test_restore_active_views_skips_guild_the_bot_has_left(db, players):
    """No view is registered when the bot is no longer in the anecdote's guild."""
    anecdote = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, content="x"
    )
    await Anecdote.update(db, anecdote.id, state="PUBLISHED", anecdote_message_id=999)
    bot = _FakeBot({}, guild=None)

    await restore_active_views(cast(discord.Client, bot), db)

    assert bot.added_views == []
