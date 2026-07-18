import psycopg
import discord

from anecbot.features.anecdote.service import (
    discard_pending_anecdotes,
    player_has_anecdotes,
)
from anecbot.models.player import Player

MAX_TARGETS = 25  # Discord select menus cap out at 25 options


async def get_active_targets(
    db: psycopg.AsyncConnection, guild_id: int, exclude_user_id: int | None = None
) -> list[Player]:
    """Return targets that can appear in the MCQ for a guild."""
    all_players = await Player.list(db, guild_id=guild_id)
    return [
        p
        for p in all_players
        if p.can_be_target
        and not p.suspended
        and not p.banned_target
        and p.user_id != exclude_user_id
    ]


async def can_register_as_target(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> bool:
    """Return whether user_id can be added as a target without exceeding the MCQ's cap."""
    active = await get_active_targets(db, guild_id, exclude_user_id=user_id)
    return len(active) < MAX_TARGETS


def get_member_guilds(bot: discord.Client, user_id: int) -> list[tuple[int, str]]:
    """Return every guild the bot shares with the user."""
    return [(guild.id, guild.name) for guild in bot.guilds if guild.get_member(user_id)]


async def is_active_submitter(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> bool:
    """Return whether the user is a non-suspended, non-banned submitter in the guild."""
    player = await Player.get(db, guild_id, user_id)
    return bool(
        player
        and player.can_submit
        and not player.suspended
        and not player.banned_submit
    )


async def cleanup_if_fully_removed(
    db: psycopg.AsyncConnection, guild_id: int, user_id: int
) -> None:
    """Discard pending anecdotes and delete the player row if they hold no roles or bans."""
    player = await Player.get(db, guild_id, user_id)
    if (
        player
        and not player.can_submit
        and not player.can_be_target
        and not player.banned_submit
        and not player.banned_target
    ):
        await discard_pending_anecdotes(db, guild_id, user_id)
        if not await player_has_anecdotes(db, guild_id, user_id):
            await Player.delete(db, guild_id, user_id)
