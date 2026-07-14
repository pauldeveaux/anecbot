from typing import Literal

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild

RevealMode = Literal["after-publish", "interval"]


async def handle(interaction: discord.Interaction, mode: RevealMode):
    """Set the reveal mode (per-anecdote offset or fixed batch interval)."""
    await Guild.upsert(get_db(interaction), interaction.guild_id, reveal_mode=mode)
    await interaction.response.send_message(
        f"✅ Mode de révélation configuré : {mode}",
        ephemeral=True,
    )
