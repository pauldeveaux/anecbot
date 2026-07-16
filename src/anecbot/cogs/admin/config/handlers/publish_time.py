import logging
import re

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild

logger = logging.getLogger(__name__)

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


async def handle(interaction: discord.Interaction, heure: str):
    """Set the publication time."""
    if not TIME_PATTERN.match(heure):
        await interaction.response.send_message(
            "❌ Format invalide. Utilise le format HH:MM (ex: 15:00).",
            ephemeral=True,
        )
        return
    await Guild.upsert(get_db(interaction), interaction.guild_id, publish_time=heure)
    logger.info("Publish time set to %s for guild %s", heure, interaction.guild_id)
    await interaction.response.send_message(
        f"✅ Heure de publication configurée : {heure}",
        ephemeral=True,
    )
