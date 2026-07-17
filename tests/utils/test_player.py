from typing import cast

import discord
import pytest

from anecbot.models.player import Player
from anecbot.utils.player import display_name

GUILD_ID = 100
USER_ID = 1


class _FakeMember:
    """Stand-in for discord.Member — only display_name is used."""

    def __init__(self, name: str):
        self.display_name = name


class _FakeGuild:
    """Stand-in for discord.Guild — only get_member is used."""

    def __init__(self, members: dict[int, _FakeMember]):
        self._members = members

    def get_member(self, user_id: int) -> _FakeMember | None:
        """Return the fake member matching the id, or None."""
        return self._members.get(user_id)


def test_display_name_prefers_alias():
    """The player's alias always wins, even if a guild member is available."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID, alias="Alice")
    guild = _FakeGuild({USER_ID: _FakeMember("Discord Name")})

    assert display_name(player, cast(discord.Guild, guild)) == "Alice"


def test_display_name_falls_back_to_guild_member():
    """Without an alias, the guild member's display name is used."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID, alias=None)
    guild = _FakeGuild({USER_ID: _FakeMember("Discord Name")})

    assert display_name(player, cast(discord.Guild, guild)) == "Discord Name"


def test_display_name_falls_back_to_user_id_when_no_guild():
    """Without an alias and no guild, the raw user id is used."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID, alias=None)

    assert display_name(player, None) == str(USER_ID)


def test_display_name_falls_back_to_user_id_when_member_not_found():
    """Without an alias, and the user isn't a cached member of the guild, falls back to id."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID, alias=None)
    guild = _FakeGuild({})

    assert display_name(player, cast(discord.Guild, guild)) == str(USER_ID)


@pytest.mark.parametrize("alias", ["", None])
def test_display_name_empty_alias_treated_as_missing(alias):
    """An empty-string alias is treated the same as no alias at all."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID, alias=alias)

    assert display_name(player, None) == str(USER_ID)
