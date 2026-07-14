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

## Tech stack

- Python 3.12+
- discord.py
- SQLite via aiosqlite
- uv (package manager)
- ruff (linter + formatter)
