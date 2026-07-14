import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild


async def handle(interaction: discord.Interaction, jours: int):
    """Set the reveal interval in active days."""
    if jours < 1:
        await interaction.response.send_message(
            "❌ L'intervalle doit être d'au moins 1 jour.",
            ephemeral=True,
        )
        return
    await Guild.upsert(
        get_db(interaction), interaction.guild_id, reveal_interval_days=jours
    )
    await interaction.response.send_message(
        f"✅ Intervalle de révélation configuré : {jours} jour(s) actif(s)",
        ephemeral=True,
    )
