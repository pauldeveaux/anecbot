ALTER TABLE guilds ADD COLUMN leaderboard_reset_in_progress INTEGER NOT NULL DEFAULT 0;

ALTER TABLE guilds ADD COLUMN leaderboard_reset_published INTEGER NOT NULL DEFAULT 0;
