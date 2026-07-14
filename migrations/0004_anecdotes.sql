CREATE TABLE anecdotes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id            INTEGER NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    author_id           INTEGER NOT NULL,
    target_id           INTEGER NOT NULL,
    content             TEXT    NOT NULL,
    state               TEXT    NOT NULL DEFAULT 'PENDING',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    published_at        TEXT,
    anecdote_message_id INTEGER,
    FOREIGN KEY (guild_id, author_id) REFERENCES players(guild_id, user_id),
    FOREIGN KEY (guild_id, target_id) REFERENCES players(guild_id, user_id)
);

CREATE INDEX idx_anecdotes_guild_state ON anecdotes(guild_id, state);
