import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.player import Player
from anecbot.shared.views.paginator import PaginatedView


async def handle(interaction: discord.Interaction):
    """List all registered players for this guild."""
    assert interaction.guild_id is not None
    db = get_db(interaction)
    players = await Player.list(db, guild_id=interaction.guild_id)

    if not players:
        await interaction.response.send_message(
            "Aucun joueur inscrit.",
            ephemeral=True,
        )
        return

    lines: list[str] = []
    for player in players:
        member = (
            interaction.guild.get_member(player.user_id) if interaction.guild else None
        )
        name = member.display_name if member else str(player.user_id)
        status = " ⏸️" if player.suspended else ""
        lines.append(f"• **{name}**{status}")

    view = PaginatedView(lines, title="Joueurs inscrits")
    await interaction.response.send_message(
        embed=view.build_embed(), view=view, ephemeral=True
    )
