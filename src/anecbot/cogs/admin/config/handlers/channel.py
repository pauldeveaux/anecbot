import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild


async def handle(interaction: discord.Interaction, channel: discord.TextChannel):
    """Set the quiz channel."""
    await Guild.upsert(get_db(interaction), interaction.guild_id, channel_id=channel.id)
    await interaction.response.send_message(
        f"✅ Channel configuré : {channel.mention}",
        ephemeral=True,
    )
