from typing import cast

import discord
import pytest

from anecbot.features.player.service import (
    MAX_TARGETS,
    can_register_as_target,
    cleanup_if_fully_removed,
    get_active_targets,
    get_member_guilds,
    is_active_submitter,
)
from anecbot.models.anecdote import Anecdote
from anecbot.models.guild import Guild
from anecbot.models.player import Player

GUILD_ID = 100
OTHER_GUILD_ID = 200


class _FakeGuild:
    """Stand-in for discord.Guild — only id/name/get_member are used by the service."""

    def __init__(self, guild_id: int, name: str, members: set[int]):
        self.id = guild_id
        self.name = name
        self._members = members

    def get_member(self, user_id: int) -> object | None:
        """Return a truthy value if user_id is a member, else None."""
        return object() if user_id in self._members else None


class _FakeBot:
    """Stand-in for discord.Client — only .guilds is used by the service."""

    def __init__(self, guilds: list[_FakeGuild]):
        self.guilds = guilds


@pytest.mark.asyncio
async def test_get_active_targets_excludes_non_targets(db):
    """Only players with can_be_target=1 are returned."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_be_target=1)
    await Player.upsert(db, GUILD_ID, 2, can_be_target=0)

    targets = await get_active_targets(db, GUILD_ID)
    assert [t.user_id for t in targets] == [1]


@pytest.mark.asyncio
async def test_get_active_targets_excludes_suspended_and_banned(db):
    """Suspended or target-banned players are excluded even if can_be_target=1."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_be_target=1, suspended=1)
    await Player.upsert(db, GUILD_ID, 2, can_be_target=1, banned_target=1)
    await Player.upsert(db, GUILD_ID, 3, can_be_target=1)

    targets = await get_active_targets(db, GUILD_ID)
    assert [t.user_id for t in targets] == [3]


@pytest.mark.asyncio
async def test_get_active_targets_excludes_given_user(db):
    """exclude_user_id removes the submitter from their own target list."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_be_target=1)
    await Player.upsert(db, GUILD_ID, 2, can_be_target=1)

    targets = await get_active_targets(db, GUILD_ID, exclude_user_id=1)
    assert [t.user_id for t in targets] == [2]


@pytest.mark.asyncio
async def test_can_register_as_target_true_under_limit(db):
    """A new user can be added as a target when under the cap."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_be_target=1)

    assert await can_register_as_target(db, GUILD_ID, 2) is True


@pytest.mark.asyncio
async def test_can_register_as_target_false_at_limit(db):
    """A new user cannot be added once MAX_TARGETS active targets already exist."""
    await Guild.upsert(db, GUILD_ID)
    for user_id in range(MAX_TARGETS):
        await Player.upsert(db, GUILD_ID, user_id, can_be_target=1)

    assert await can_register_as_target(db, GUILD_ID, MAX_TARGETS) is False


@pytest.mark.asyncio
async def test_can_register_as_target_true_for_already_active_target(db):
    """A user who is already an active target isn't blocked by their own slot."""
    await Guild.upsert(db, GUILD_ID)
    for user_id in range(MAX_TARGETS):
        await Player.upsert(db, GUILD_ID, user_id, can_be_target=1)

    assert await can_register_as_target(db, GUILD_ID, 0) is True


def test_get_member_guilds_returns_only_shared_guilds():
    """Only guilds where the bot has the user as a member are returned."""
    bot = _FakeBot(
        [
            _FakeGuild(GUILD_ID, "Guild A", members={1}),
            _FakeGuild(OTHER_GUILD_ID, "Guild B", members={2}),
        ]
    )

    guilds = get_member_guilds(cast(discord.Client, bot), 1)
    assert guilds == [(GUILD_ID, "Guild A")]


def test_get_member_guilds_empty_when_no_shared_guild():
    """Returns an empty list when the bot shares no guild with the user."""
    bot = _FakeBot([_FakeGuild(GUILD_ID, "Guild A", members={2})])

    guilds = get_member_guilds(cast(discord.Client, bot), 1)
    assert guilds == []


@pytest.mark.asyncio
async def test_is_active_submitter_true_for_active_submitter(db):
    """Returns True for a registered, non-suspended, non-banned submitter."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=1)

    assert await is_active_submitter(db, GUILD_ID, 1) is True


@pytest.mark.asyncio
async def test_is_active_submitter_false_when_not_registered(db):
    """Returns False when the user has no player row in the guild."""
    await Guild.upsert(db, GUILD_ID)

    assert await is_active_submitter(db, GUILD_ID, 1) is False


@pytest.mark.asyncio
async def test_is_active_submitter_false_when_not_a_submitter(db):
    """Returns False when the player is not registered as a submitter."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=0)

    assert await is_active_submitter(db, GUILD_ID, 1) is False


@pytest.mark.asyncio
async def test_is_active_submitter_false_when_suspended_or_banned(db):
    """Returns False for a suspended or submit-banned submitter."""
    await Guild.upsert(db, GUILD_ID)
    await Guild.upsert(db, OTHER_GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=1, suspended=1)
    await Player.upsert(db, OTHER_GUILD_ID, 1, can_submit=1, banned_submit=1)

    assert await is_active_submitter(db, GUILD_ID, 1) is False
    assert await is_active_submitter(db, OTHER_GUILD_ID, 1) is False


@pytest.mark.asyncio
async def test_cleanup_if_fully_removed_deletes_player_with_no_roles_or_bans(db):
    """A player with no roles, no bans, and no anecdotes is deleted."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=0, can_be_target=0)

    await cleanup_if_fully_removed(db, GUILD_ID, 1)

    assert await Player.get(db, GUILD_ID, 1) is None


@pytest.mark.asyncio
async def test_cleanup_if_fully_removed_keeps_player_with_a_ban(db):
    """A player with an active ban is kept even with no roles."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=0, can_be_target=0, banned_submit=1)

    await cleanup_if_fully_removed(db, GUILD_ID, 1)

    assert await Player.get(db, GUILD_ID, 1) is not None


@pytest.mark.asyncio
async def test_cleanup_if_fully_removed_keeps_player_with_a_role(db):
    """A player who still holds a role is left untouched."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=1, can_be_target=0)

    await cleanup_if_fully_removed(db, GUILD_ID, 1)

    assert await Player.get(db, GUILD_ID, 1) is not None


@pytest.mark.asyncio
async def test_cleanup_if_fully_removed_discards_pending_but_keeps_row_with_history(db):
    """Pending anecdotes are discarded, but the player row survives if they have history."""
    await Guild.upsert(db, GUILD_ID)
    await Player.upsert(db, GUILD_ID, 1, can_submit=0, can_be_target=0)
    await Player.upsert(db, GUILD_ID, 2, can_be_target=1)
    pending = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=1, target_id=2, content="x"
    )
    published = await Anecdote.create(
        db, guild_id=GUILD_ID, author_id=1, target_id=2, content="y"
    )
    await Anecdote.update(db, published.id, state="PUBLISHED")

    await cleanup_if_fully_removed(db, GUILD_ID, 1)

    assert await Anecdote.get(db, pending.id) is None
    assert await Anecdote.get(db, published.id) is not None
    assert await Player.get(db, GUILD_ID, 1) is not None
