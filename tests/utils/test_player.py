from typing import cast

import discord

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


def test_display_name_uses_guild_member():
    """When the user is a cached guild member, their display name is used."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID)
    guild = _FakeGuild({USER_ID: _FakeMember("Discord Name")})

    assert display_name(player, cast(discord.Guild, guild)) == "Discord Name"


def test_display_name_falls_back_to_user_id_when_no_guild():
    """Without a guild, the raw user id is used."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID)

    assert display_name(player, None) == str(USER_ID)


def test_display_name_falls_back_to_user_id_when_member_not_found():
    """When the user isn't a cached member of the guild, falls back to id."""
    player = Player(guild_id=GUILD_ID, user_id=USER_ID)
    guild = _FakeGuild({})

    assert display_name(player, cast(discord.Guild, guild)) == str(USER_ID)
