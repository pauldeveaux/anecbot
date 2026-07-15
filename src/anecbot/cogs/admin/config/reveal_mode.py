import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.enums import RevealMode
from anecbot.models.guild import Guild

MODE_LABELS: dict[RevealMode, str] = {
    RevealMode.AFTER_PUBLISH: "après publication",
    RevealMode.INTERVAL: "par intervalle",
}


async def handle(interaction: discord.Interaction, mode: RevealMode):
    """Set the reveal mode (per-anecdote offset or fixed batch interval)."""
    await Guild.upsert(get_db(interaction), interaction.guild_id, reveal_mode=mode)
    await interaction.response.send_message(
        f"✅ Mode de révélation configuré : {MODE_LABELS[mode]}",
        ephemeral=True,
    )
