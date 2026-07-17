import discord

from anecbot.cogs.admin.base import get_db
from anecbot.utils.player import display_name
from anecbot.models.enums import PlayerFilter
from anecbot.models.player import Player
from anecbot.shared.views.paginator import PaginatedView

FILTER_TITLES = {
    None: "Joueurs inscrits",
    PlayerFilter.SUBMITTER: "Rédacteurs d'anecdotes",
    PlayerFilter.TARGET: "Cibles d'anecdotes",
    PlayerFilter.BANNED: "Joueurs bannis",
}


def _matches_filter(player: Player, filter_role: str | None) -> bool:
    """Check if a player matches the given filter."""
    if filter_role is None:
        return True
    if filter_role == PlayerFilter.SUBMITTER:
        return bool(player.can_submit)
    if filter_role == PlayerFilter.TARGET:
        return bool(player.can_be_target)
    if filter_role == PlayerFilter.BANNED:
        return bool(player.banned_submit or player.banned_target)
    return True


def _format_player(
    player: Player, guild: discord.Guild | None, filter_role: str | None
) -> str:
    """Format a single player line."""
    name = display_name(player, guild)

    status = ""
    if player.suspended:
        status += " ⏸️"
    if filter_role == PlayerFilter.BANNED:
        parts = []
        if player.banned_submit:
            parts.append("rédacteur")
        if player.banned_target:
            parts.append("cible")
        status += f" ({', '.join(parts)})"

    return f"• **{name}**{status}"


async def handle(
    interaction: discord.Interaction, filter_role: str | None = None
) -> None:
    """List players, optionally filtered by role."""
    assert interaction.guild_id is not None
    db = get_db(interaction)
    all_players = await Player.list(db, guild_id=interaction.guild_id)

    players = [p for p in all_players if _matches_filter(p, filter_role)]

    if not players:
        await interaction.response.send_message(
            "Aucun joueur trouvé.",
            ephemeral=True,
        )
        return

    lines = [_format_player(p, interaction.guild, filter_role) for p in players]
    title = FILTER_TITLES.get(filter_role, "Joueurs")

    view = PaginatedView(lines, title=title)
    await interaction.response.send_message(
        embed=view.build_embed(), view=view, ephemeral=True
    )
