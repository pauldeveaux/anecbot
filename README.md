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

# Run
uv run python -m anecbot
```

## Configuration

Set via environment variables (`.env`, see `.env.example`):

| Variable | Default | Description |
| --- | --- | --- |
| `DISCORD_TOKEN` | — (required) | Discord bot token |
| `DB_PATH` | `data/anecbot.db` | SQLite database file |
| `MIGRATIONS_DIR` | `migrations` | Directory of versioned SQL migration files |
| `LOG_LEVEL` | `INFO` | Log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`, ...); invalid values fall back to `INFO` |
| `LOG_FILE` | `data/anecbot.log` | Log file path |

## Logs

Logs are written both to the console (colored) and to `LOG_FILE` (plain text). The log file rotates
automatically at 5 MB, keeping 3 backups (`anecbot.log`, `anecbot.log.1`, `anecbot.log.2`,
`anecbot.log.3`).

To see more detail (e.g. per-interaction logs), set `LOG_LEVEL=DEBUG` in `.env` and restart the bot.

## Tech stack

- Python 3.14+
- discord.py
- SQLite via aiosqlite
- uv (package manager)
- ruff (linter + formatter)
- pyright (type checker)
