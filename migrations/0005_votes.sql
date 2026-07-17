CREATE TABLE votes (
    anecdote_id  INTEGER NOT NULL REFERENCES anecdotes(id) ON DELETE CASCADE,
    user_id      INTEGER NOT NULL,
    voted_for_id INTEGER NOT NULL,
    voted_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (anecdote_id, user_id)
);
