import discord

from anecbot.features.rules.service import build_rules_embed


async def handle(interaction: discord.Interaction):
    """Show the game rules as an ephemeral reply."""
    embed = build_rules_embed()
    await interaction.response.send_message(embed=embed, ephemeral=True)
