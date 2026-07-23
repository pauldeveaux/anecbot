CREATE TABLE anecdote_media (
    id SERIAL PRIMARY KEY,
    anecdote_id INTEGER NOT NULL REFERENCES anecdotes(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    media_url TEXT NOT NULL,
    dm_channel_id BIGINT,
    dm_message_id BIGINT,
    attachment_index INTEGER
);
