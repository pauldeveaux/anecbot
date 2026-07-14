# AnecBot — Specifications

## Multi-server

- Each Discord server has its own configuration and data
- Full isolation between servers

## Per-server configuration

- Broadcast channel
- Publish interval (in days)
- Publish time (HH:MM)
- Days off (e.g. Saturday/Sunday) — publication is postponed to the next active day, but days off still count toward the interval
- Leaderboard reset interval (0 = no reset)
- Anecdote limit per person per day (0 = unlimited)
- Reveal interval (default: 1 day)
- Reveal time (HH:MM)
- Player registration for answers (independent from anecdote submission)

## Anecdote submission (via DM)

1. Player sends a DM to the bot
2. Server selection (if on multiple servers with the bot)
3. Target user selection (among registered players)
4. Anecdote input and confirmation

## Publication

- Weighted random selection: older anecdotes have higher chances of being picked
- Per-person balancing: if a user comes up too often, their probability decreases
- Anecdote + MCQ (Discord form) published in the configured channel
- If the queue is empty, the bot sends a warning message
- A published anecdote cannot be republished

## Reveal

- Includes the original anecdote in the message
- Shows received votes
- Reveals the answer in spoiler
- If multiple anecdotes were published since the last reveal, they are all revealed at once
- If no anecdote was published, the reveal interval restarts from the next publication
- Updates and publishes the leaderboard (only once if multiple simultaneous reveals)

## Batch

- Runs every minute
- Idempotent state machine: `PENDING → RUNNING → PUBLISHED → REVEALED`
- Handles publications, reveals, and leaderboard resets
