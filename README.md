# AnecBot

Discord quiz bot based on player-submitted anecdotes.

## What is it?

Players submit anecdotes about other server members via DM to the bot. The bot publishes these anecdotes at regular intervals in a dedicated channel, along with a multiple-choice quiz (Discord form) to guess who the anecdote belongs to. Answers are revealed after a configurable delay, and a leaderboard tracks scores.

See [SPECS.md](SPECS.md) for detailed features and game mechanics.

## Getting started

```bash
# Install dependencies
uv sync

# Configure
cp .env.example .env
# Set DISCORD_TOKEN in .env

# Start a local Postgres (used by both the bot and the test suite)
docker compose up -d db

# Run
uv run python -m anecbot
```

## Configuration

Set via environment variables (`.env`, see `.env.example`):

| Variable | Default | Description |
| --- | --- | --- |
| `DISCORD_TOKEN` | — (required) | Discord bot token |
| `DATABASE_URL` | — (required) | PostgreSQL connection string |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | — (required) | Credentials for the `db` container (docker-compose only) |
| `MIGRATIONS_DIR` | `migrations` | Directory of versioned SQL migration files |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, ...); invalid values fall back to `INFO` |
| `LOG_FILE` | `data/anecbot.log` | Log file path |

## Deployment (Docker)

`docker-compose.yml` provisions both the bot and its PostgreSQL database — nothing needs to be
installed on the VPS beyond Docker itself.

First-time setup on the VPS:

```bash
git clone <repo-url>
cd anecbot
cp .env.example .env
# Set DISCORD_TOKEN, and change POSTGRES_PASSWORD to a real secret (DATABASE_URL must use the
# same password — docker-compose fills the "db" host in automatically for the bot container)

# The container runs as uid 1000; the bind-mounted data dir must be writable by it
mkdir -p data && sudo chown 1000:1000 data

docker compose up -d --build
```

This starts two containers: `anecbot` and `db` (Postgres). `db`'s data lives in the named Docker
volume `pgdata`, so it survives `docker compose down` and image rebuilds — only `docker compose down
-v` or `docker volume rm` deletes it. Postgres's port (5432) is bound to `127.0.0.1` only, so it's
reachable from the VPS itself (e.g. for `pg_dump`) but never exposed to the internet.
`restart: unless-stopped` restarts either container if it crashes or the VPS reboots.

**Backups**: since the game data now lives in the `pgdata` volume instead of a single file, back it
up with `pg_dump` rather than copying a file:

```bash
docker compose exec db pg_dump -U anecbot anecbot > backup-$(date +%F).sql
```

To restore: `cat backup.sql | docker compose exec -T db psql -U anecbot anecbot`.

To update after pulling new changes:

```bash
git pull
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f
```

## Logs

Logs are written both to the console (colored) and to `LOG_FILE` (plain text). The log file rotates
automatically at 5 MB, keeping 3 backups (`anecbot.log`, `anecbot.log.1`, `anecbot.log.2`,
`anecbot.log.3`).

To see more detail (e.g. per-interaction logs), set `LOG_LEVEL=DEBUG` in `.env` and restart the bot.

## Tech stack

- Python 3.14+
- discord.py
- PostgreSQL via psycopg
- uv (package manager)
- ruff (linter + formatter)
- pyright (type checker)
