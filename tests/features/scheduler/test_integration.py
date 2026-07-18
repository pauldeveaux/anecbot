from typing import cast

import discord
import pytest

from anecbot.features.scheduler.service import check_publications, check_reveals
from anecbot.models.anecdote import Anecdote
from anecbot.models.enums import GuildTimezone
from anecbot.models.guild import Guild
from anecbot.models.leaderboard import LeaderboardEntry
from anecbot.models.player import Player
from anecbot.models.vote import Vote
from anecbot.utils.time import utcnow

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
    """Stand-in for a Messageable channel — records sends, returns fake messages."""

    def __init__(self):
        self.sent_embeds: list[discord.Embed | None] = []
        self._messages: dict[int, _FakeMessage] = {}

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


@pytest.mark.asyncio
async def test_full_publish_vote_reveal_cycle(db):
    """PENDING -> check_publications -> vote -> check_reveals ends REVEALED with points awarded."""
    # publish_time/reveal_time="00:00" and interval=0/days_off="" so the due-checks pass
    # regardless of the real wall-clock moment the test happens to run at — publish_and_open_voting
    # stamps published_at using the real utcnow() internally (it has no injectable "now"), so the
    # due-checks here are deliberately time-of-day-independent rather than pinned to a fake instant.
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=CHANNEL_ID,
        started=1,
        publish_time="00:00",
        reveal_interval_days=0,
        reveal_time="00:00",
        timezone=GuildTimezone.UTC,
    )
    await Player.upsert(db, GUILD_ID, AUTHOR_ID, can_submit=1)
    await Player.upsert(db, GUILD_ID, TARGET_ID, can_be_target=1)
    await Player.upsert(db, GUILD_ID, VOTER_ID, can_submit=1)
    await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=AUTHOR_ID, target_id=TARGET_ID, content="x"
    )
    channel = _FakeChannel()
    bot = _FakeBot({CHANNEL_ID: channel})

    triggered = await check_publications(cast(discord.Client, bot), db, utcnow())
    assert triggered == 1

    published = await Anecdote.list(db, guild_id=GUILD_ID, state="PUBLISHED")
    assert len(published) == 1
    anecdote = published[0]

    await Vote.upsert(db, anecdote.id, VOTER_ID, voted_for_id=TARGET_ID)

    total_revealed = await check_reveals(cast(discord.Client, bot), db, utcnow())
    assert total_revealed == 1

    final = await Anecdote.get(db, anecdote.id)
    assert final is not None
    assert final.state == "REVEALED"
    assert final.reveal_message_id is not None

    voter_entry = await LeaderboardEntry.get(db, GUILD_ID, VOTER_ID)
    assert voter_entry is not None
    assert voter_entry.points == 1
    author_entry = await LeaderboardEntry.get(db, GUILD_ID, AUTHOR_ID)
    assert author_entry is not None
    assert author_entry.points == 1

    # embed 1 = the anecdote announcement, embed 2 = the post-reveal leaderboard
    assert len(channel.sent_embeds) == 2
