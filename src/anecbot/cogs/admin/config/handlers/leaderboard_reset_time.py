import re

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def handle(interaction: discord.Interaction, heure: str):
    """Set the leaderboard reset time."""
    if not TIME_PATTERN.match(heure):
        await interaction.response.send_message(
            "❌ Format invalide. Utilise le format HH:MM (ex: 00:00).",
            ephemeral=True,
        )
        return
    await Guild.upsert(
        get_db(interaction), interaction.guild_id, leaderboard_reset_time=heure
    )
    await interaction.response.send_message(
        f"✅ Heure de reset du leaderboard configurée : {heure}",
        ephemeral=True,
    )
