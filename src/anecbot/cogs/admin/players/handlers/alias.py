import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.player import Player


async def handle(
    interaction: discord.Interaction, user: discord.Member, name: str
) -> None:
    """Set a display alias for a player."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    existing = await Player.get(db, interaction.guild_id, user.id)
    if existing is None:
        await interaction.response.send_message(
            f"❌ {user.mention} n'est pas inscrit(e).",
            ephemeral=True,
        )
        return

    await Player.update(db, interaction.guild_id, user.id, alias=name)
    await interaction.response.send_message(
        f"✅ Alias de {user.mention} défini : **{name}**",
        ephemeral=True,
    )
