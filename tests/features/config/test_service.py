from pathlib import Path

import aiosqlite
import pytest
import pytest_asyncio

from anecbot.features.config.service import DEFAULT_GUILD_CONFIG, reset_guild_config
from anecbot.models.database import run_migrations
from anecbot.models.enums import GuildTimezone, LeaderboardResetMode
from anecbot.models.guild import Guild

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"
GUILD_ID = 100


@pytest_asyncio.fixture
async def db():
    """Provide an in-memory database with migrations applied."""
    conn = await aiosqlite.connect(":memory:")
    await conn.execute("PRAGMA foreign_keys=ON")
    await run_migrations(conn, MIGRATIONS_DIR)
    yield conn
    await conn.close()


@pytest.mark.asyncio
async def test_reset_guild_config_restores_defaults(db):
    """A fully customized guild's config is reset back to every default value."""
    await Guild.upsert(
        db,
        GUILD_ID,
        channel_id=123,
        interval_days=5,
        publish_time="09:00",
        days_off="sat,sun",
        reveal_interval_days=2,
        reveal_time="20:00",
        timezone=GuildTimezone.AMERICA_NEW_YORK,
        leaderboard_reset_mode=LeaderboardResetMode.WEEKLY,
        leaderboard_reset_interval=2,
        leaderboard_reset_anchor=3,
        leaderboard_reset_time="12:00",
        daily_limit=10,
        started=1,
    )

    result = await reset_guild_config(db, GUILD_ID)

    for column, value in DEFAULT_GUILD_CONFIG.items():
        assert getattr(result, column) == value
