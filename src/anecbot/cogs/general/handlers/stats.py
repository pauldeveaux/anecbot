import discord

from anecbot.features.stats.service import (
    GuildStats,
    PlayerStats,
    get_guild_stats,
    get_player_stats,
)
from anecbot.utils.time import discord_timestamp


def build_stats_embed(stats: GuildStats) -> discord.Embed:
    """Build an embed with game statistics."""
    state_label = "En cours" if stats.started else "Arrêté"
    state_emoji = "\U0001f7e2" if stats.started else "\U0001f534"

    embed = discord.Embed(
        title="Statistiques du jeu",
        color=discord.Color.green() if stats.started else discord.Color.red(),
    )

    started_value = f"{state_emoji} {state_label}"
    if stats.started_at:
        started_value += f"\nDepuis le {discord_timestamp(stats.started_at)}"
    embed.add_field(name="État", value=started_value, inline=False)

    embed.add_field(
        name="Anecdotes",
        value=(
            f"**{stats.anecdotes_total}** au total\n"
            f"{stats.anecdotes_pending} en attente\n"
            f"{stats.anecdotes_published} publiée(s)\n"
            f"{stats.anecdotes_revealed} révélée(s)"
        ),
        inline=True,
    )

    embed.add_field(
        name="Joueurs",
        value=(
            f"**{stats.players_total}** au total\n"
            f"{stats.players_submitters} rédacteur(s)\n"
            f"{stats.players_targets} cible(s)"
        ),
        inline=True,
    )

    return embed


async def handle(interaction: discord.Interaction):
    """Show game statistics for this guild."""
    assert interaction.guild_id is not None
    db = interaction.client.db  # type: ignore[attr-defined]
    stats = await get_guild_stats(db, interaction.guild_id)
    embed = build_stats_embed(stats)
    await interaction.response.send_message(embed=embed, ephemeral=True)


def build_player_stats_embed(
    stats: PlayerStats, member: discord.Member | discord.User
) -> discord.Embed:
    """Build an embed with a single player's points, rank, and voting/anecdote statistics."""
    embed = discord.Embed(
        title=f"Statistiques de {member.display_name}",
        color=discord.Color.blue(),
    )

    rank_value = f"{stats.rank}ᵉ" if stats.rank is not None else "Non classé"
    embed.add_field(
        name="🏆 Classement",
        value=f"**{stats.points}** pt(s) — {rank_value}",
        inline=False,
    )

    rating_value = (
        f"{stats.average_rating:.1f}/5" if stats.average_rating is not None else "—"
    )
    embed.add_field(
        name="✍️ Anecdotes révélée(s)",
        value=f"Total : {stats.revealed_count}\nNote moyenne : {rating_value}",
        inline=False,
    )

    accuracy_value = (
        f"{stats.accuracy_pct:.0f}%" if stats.accuracy_pct is not None else "—"
    )
    embed.add_field(
        name="🗳️ Votes",
        value=(
            f"Votes : {stats.votes_cast}\n"
            f"Votes corrects : {stats.correct_votes}\n"
            f"Précision : {accuracy_value}"
        ),
        inline=False,
    )

    return embed


async def handle_player(interaction: discord.Interaction, user: discord.Member):
    """Show a single player's statistics for this guild."""
    assert interaction.guild_id is not None
    db = interaction.client.db  # type: ignore[attr-defined]
    stats = await get_player_stats(db, interaction.guild_id, user.id)
    embed = build_player_stats_embed(stats, user)
    await interaction.response.send_message(embed=embed, ephemeral=True)
