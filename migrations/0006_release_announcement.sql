CREATE TABLE release_announcement (
    id            INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    content_hash  TEXT,
    announced_at  TEXT
);
