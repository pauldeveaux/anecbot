CREATE TABLE guilds (
    guild_id                        BIGINT PRIMARY KEY,
    channel_id                      BIGINT,
    interval_days                   INTEGER NOT NULL DEFAULT 1,
    publish_time                    TEXT NOT NULL DEFAULT '15:00',
    days_off                        TEXT NOT NULL DEFAULT '',
    reveal_interval_days            INTEGER NOT NULL DEFAULT 1,
    reveal_time                     TEXT NOT NULL DEFAULT '13:30',
    leaderboard_reset_mode          TEXT NOT NULL DEFAULT 'never',
    leaderboard_reset_interval      INTEGER NOT NULL DEFAULT 1,
    leaderboard_reset_anchor        INTEGER,
    leaderboard_reset_time          TEXT NOT NULL DEFAULT '00:00',
    daily_limit                     INTEGER NOT NULL DEFAULT 0,
    started                         INTEGER NOT NULL DEFAULT 0,
    started_at                      TEXT,
    queue_empty_warned              INTEGER NOT NULL DEFAULT 0,
    last_leaderboard_reset_at       TEXT,
    timezone                        TEXT NOT NULL DEFAULT 'Europe/Paris',
    leaderboard_reset_in_progress   INTEGER NOT NULL DEFAULT 0,
    leaderboard_reset_published     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE players (
    guild_id      BIGINT NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id       BIGINT NOT NULL,
    can_submit    INTEGER NOT NULL DEFAULT 0,
    can_be_target INTEGER NOT NULL DEFAULT 0,
    suspended     INTEGER NOT NULL DEFAULT 0,
    banned_submit INTEGER NOT NULL DEFAULT 0,
    banned_target INTEGER NOT NULL DEFAULT 0,
    registered_at TEXT    NOT NULL DEFAULT ((now() AT TIME ZONE 'utc')::text),
    PRIMARY KEY (guild_id, user_id)
);

CREATE TABLE anecdotes (
    id                  INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    guild_id            BIGINT  NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    author_id           BIGINT  NOT NULL,
    target_id           BIGINT  NOT NULL,
    content             TEXT    NOT NULL,
    state               TEXT    NOT NULL DEFAULT 'PENDING',
    created_at          TEXT    NOT NULL DEFAULT ((now() AT TIME ZONE 'utc')::text),
    published_at        TEXT,
    anecdote_message_id BIGINT,
    reveal_message_id   BIGINT,
    points_awarded      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (guild_id, author_id) REFERENCES players(guild_id, user_id),
    FOREIGN KEY (guild_id, target_id) REFERENCES players(guild_id, user_id)
);

CREATE INDEX idx_anecdotes_guild_state ON anecdotes(guild_id, state);

CREATE TABLE votes (
    anecdote_id  INTEGER NOT NULL REFERENCES anecdotes(id) ON DELETE CASCADE,
    user_id      BIGINT  NOT NULL,
    voted_for_id BIGINT  NOT NULL,
    voted_at     TEXT    NOT NULL DEFAULT ((now() AT TIME ZONE 'utc')::text),
    guild_id     BIGINT  REFERENCES guilds(guild_id) ON DELETE CASCADE,
    PRIMARY KEY (anecdote_id, user_id)
);

CREATE INDEX idx_votes_guild ON votes(guild_id);

CREATE TABLE leaderboard (
    guild_id BIGINT  NOT NULL REFERENCES guilds(guild_id) ON DELETE CASCADE,
    user_id  BIGINT  NOT NULL,
    points   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
