import discord

from anecbot.models.player import Player


def display_name(player: Player, guild: discord.Guild | None) -> str:
    """Return the player's alias, or their Discord display name, or their user ID."""
    if player.alias:
        return player.alias
    if guild:
        member = guild.get_member(player.user_id)
        if member:
            return member.display_name
    return str(player.user_id)
