"""TEMPORARY debug command — force a fake batch tick (publish + reveal) for manual testing.

Must be deleted once ANEC-22 wires up the real scheduler.
"""

import discord
from discord import app_commands

from anecbot.cogs.admin.base import AdminCog, get_db
from anecbot.features.leaderboard.service import publish_leaderboard
from anecbot.features.publisher.service import publish_and_open_voting
from anecbot.features.revealer.service import reveal_anecdote
from anecbot.models.anecdote import Anecdote


class DebugBatchCog(AdminCog):
    """TEMPORARY: force-publish the next anecdote and force-reveal every PUBLISHED one."""

    @app_commands.command(
        name="debug-batch",
        description="[TEMP] Force un tick de batch (publication + révélation)",
    )
    async def debug_batch(self, interaction: discord.Interaction):
        """Force-reveal anecdotes PUBLISHED before this call, then force-publish the next one."""
        assert interaction.guild_id is not None
        db = get_db(interaction)
        bot = interaction.client

        # Reveal BEFORE publishing: otherwise the anecdote we're about to publish would
        # immediately show up as PUBLISHED and get force-revealed in the same call, leaving
        # no window to vote on it between two /debug-batch runs.
        to_reveal = await Anecdote.list(
            db, guild_id=interaction.guild_id, state="PUBLISHED"
        )
        revealed = [await reveal_anecdote(bot, db, anecdote) for anecdote in to_reveal]
        if revealed:
            await publish_leaderboard(bot, db, interaction.guild_id)

        published = await publish_and_open_voting(bot, db, interaction.guild_id)

        lines = [
            f"🔍 Révélé : {len(revealed)} anecdote(s)",
            f"📢 Publié : {'#' + str(published.id) if published else 'rien'}",
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)
