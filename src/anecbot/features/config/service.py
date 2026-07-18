import psycopg

from anecbot.models.enums import GuildTimezone, LeaderboardResetMode
from anecbot.models.guild import Guild

DEFAULT_GUILD_CONFIG: dict[str, object] = {
    "channel_id": None,
    "interval_days": 1,
    "publish_time": "15:00",
    "days_off": "",
    "reveal_interval_days": 1,
    "reveal_time": "13:30",
    "timezone": GuildTimezone.EUROPE_PARIS,
    "leaderboard_reset_mode": LeaderboardResetMode.NEVER,
    "leaderboard_reset_interval": 1,
    "leaderboard_reset_anchor": None,
    "leaderboard_reset_time": "00:00",
    "daily_limit": 0,
    "started": 0,
}


async def reset_guild_config(db: psycopg.AsyncConnection, guild_id: int) -> Guild:
    """Reset guild configuration to defaults and stop the game."""
    return await Guild.upsert(db, guild_id, **DEFAULT_GUILD_CONFIG)
