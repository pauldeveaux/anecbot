CREATE TABLE anecdote_quality_votes (
    anecdote_id INTEGER NOT NULL REFERENCES anecdotes(id) ON DELETE CASCADE,
    user_id     BIGINT  NOT NULL,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    voted_at    TEXT    NOT NULL DEFAULT ((now() AT TIME ZONE 'utc')::text),
    guild_id    BIGINT  REFERENCES guilds(guild_id) ON DELETE CASCADE,
    PRIMARY KEY (anecdote_id, user_id)
);

CREATE INDEX idx_anecdote_quality_votes_guild ON anecdote_quality_votes(guild_id);
