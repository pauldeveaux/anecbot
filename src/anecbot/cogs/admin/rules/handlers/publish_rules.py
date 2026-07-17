from typing import cast

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.rules.service import build_rules_embed
from anecbot.models.guild import Guild


async def handle(interaction: discord.Interaction):
    """Publish the game rules in the guild's configured channel."""
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id)

    if guild is None or guild.channel_id is None:
        await interaction.response.send_message(
            "❌ Configure d'abord un channel avec `/config channel`.",
            ephemeral=True,
        )
        return

    channel = cast(
        "discord.abc.Messageable | None",
        interaction.client.get_channel(guild.channel_id),
    )
    if channel is None:
        await interaction.response.send_message(
            "❌ Le channel configuré est introuvable.",
            ephemeral=True,
        )
        return

    embed = build_rules_embed()
    await channel.send(embed=embed)
    await interaction.response.send_message(
        "✅ Règles publiées.",
        ephemeral=True,
    )
