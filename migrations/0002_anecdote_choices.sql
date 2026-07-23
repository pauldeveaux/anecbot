CREATE TABLE anecdote_choices (
    id          INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    anecdote_id INTEGER NOT NULL REFERENCES anecdotes(id) ON DELETE CASCADE,
    label       TEXT    NOT NULL,
    is_correct  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_anecdote_choices_anecdote ON anecdote_choices(anecdote_id);

-- Backfill existing anecdotes so in-flight PENDING/PUBLISHED/REVEALING ones keep working once
-- target_id is dropped below: the anecdote's own target becomes its correct choice, and every
-- other active target in the same guild (at migration time) becomes a wrong choice, matching the
-- live MCQ each PUBLISHED anecdote already has. Labels fall back to the raw user id as text since
-- Discord display names aren't reachable from SQL, consistent with the app's existing fallback
-- to the raw id when a member can't be resolved.
INSERT INTO anecdote_choices (anecdote_id, label, is_correct)
SELECT id, target_id::text, 1 FROM anecdotes;

INSERT INTO anecdote_choices (anecdote_id, label, is_correct)
SELECT a.id, p.user_id::text, 0
FROM anecdotes a
JOIN players p
  ON p.guild_id = a.guild_id
 AND p.can_be_target = 1
 AND p.suspended = 0
 AND p.banned_target = 0
 AND p.user_id != a.target_id;

ALTER TABLE anecdotes DROP COLUMN target_id;
