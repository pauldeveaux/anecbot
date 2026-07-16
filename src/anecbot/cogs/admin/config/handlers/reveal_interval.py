import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.publisher.service import refresh_published_reveal_dates
from anecbot.models.guild import Guild


async def handle(interaction: discord.Interaction, jours: int):
    """Set the reveal interval in active days."""
    assert interaction.guild_id is not None
    if jours < 1:
        await interaction.response.send_message(
            "❌ L'intervalle doit être d'au moins 1 jour.",
            ephemeral=True,
        )
        return
    db = get_db(interaction)
    await Guild.upsert(db, interaction.guild_id, reveal_interval_days=jours)
    await refresh_published_reveal_dates(interaction.client, db, interaction.guild_id)
    await interaction.response.send_message(
        f"✅ Intervalle de révélation configuré : {jours} jour(s) actif(s)",
        ephemeral=True,
    )
