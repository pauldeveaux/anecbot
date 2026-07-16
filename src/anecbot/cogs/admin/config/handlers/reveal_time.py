import re

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.publisher.service import refresh_published_reveal_dates
from anecbot.models.guild import Guild

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def handle(interaction: discord.Interaction, heure: str):
    """Set the reveal time."""
    assert interaction.guild_id is not None
    if not TIME_PATTERN.match(heure):
        await interaction.response.send_message(
            "❌ Format invalide. Utilise le format HH:MM (ex: 13:30).",
            ephemeral=True,
        )
        return
    db = get_db(interaction)
    await Guild.upsert(db, interaction.guild_id, reveal_time=heure)
    await refresh_published_reveal_dates(interaction.client, db, interaction.guild_id)
    await interaction.response.send_message(
        f"✅ Heure de révélation configurée : {heure}",
        ephemeral=True,
    )
