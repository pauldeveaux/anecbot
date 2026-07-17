CREATE TABLE leaderboard (
    guild_id INTEGER NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id  INTEGER NOT NULL,
    points   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
