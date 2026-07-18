import discord

from anecbot.models.player import Player


def display_name(player: Player, guild: discord.Guild | None) -> str:
    """Return the player's Discord display name, or their user ID if unavailable."""
    if guild:
        member = guild.get_member(player.user_id)
        if member:
            return member.display_name
    return str(player.user_id)
