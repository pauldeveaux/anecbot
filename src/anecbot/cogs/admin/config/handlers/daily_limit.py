import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild


async def handle(interaction: discord.Interaction, n: int):
    """Set the daily anecdote submission limit per person."""
    assert interaction.guild_id is not None
    if n < 0:
        await interaction.response.send_message(
            "❌ La limite doit être 0 (illimité) ou plus.",
            ephemeral=True,
        )
        return
    await Guild.upsert(get_db(interaction), interaction.guild_id, daily_limit=n)
    label = str(n) if n else "illimitée"
    await interaction.response.send_message(
        f"✅ Limite quotidienne configurée : {label}",
        ephemeral=True,
    )
