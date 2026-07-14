CREATE TABLE guilds (
    guild_id INTEGER PRIMARY KEY,
    channel_id INTEGER,
    interval_days INTEGER NOT NULL DEFAULT 1,
    publish_time TEXT NOT NULL DEFAULT '15:00',
    days_off TEXT NOT NULL DEFAULT '',
    reveal_interval_days INTEGER NOT NULL DEFAULT 1,
    reveal_time TEXT NOT NULL DEFAULT '13:30',
    leaderboard_reset_days INTEGER NOT NULL DEFAULT 0,
    daily_limit INTEGER NOT NULL DEFAULT 0
);
