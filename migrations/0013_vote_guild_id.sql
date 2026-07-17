ALTER TABLE votes ADD COLUMN guild_id INTEGER REFERENCES guilds(guild_id) ON DELETE CASCADE;

UPDATE votes SET guild_id = (
    SELECT anecdotes.guild_id FROM anecdotes WHERE anecdotes.id = votes.anecdote_id
);

CREATE INDEX idx_votes_guild ON votes(guild_id);
