CREATE TABLE players (
    guild_id      INTEGER NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id       INTEGER NOT NULL,
    can_submit    INTEGER NOT NULL DEFAULT 0,
    can_be_target INTEGER NOT NULL DEFAULT 0,
    alias         TEXT,
    suspended     INTEGER NOT NULL DEFAULT 0,
    banned_submit INTEGER NOT NULL DEFAULT 0,
    banned_target INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (guild_id, user_id)
);
