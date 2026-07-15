from pathlib import Path
from typing import cast

import aiosqlite
import discord
import pytest
import pytest_asyncio

from anecbot.features.player.service import (
    get_active_targets,
    get_member_guilds,
    is_active_submitter,
)
from anecbot.models.database import run_migrations
from anecbot.models.guild import Guild
from anecbot.models.player import Player

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
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


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


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
