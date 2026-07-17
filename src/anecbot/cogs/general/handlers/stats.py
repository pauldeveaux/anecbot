import discord

from anecbot.features.stats.service import GuildStats, get_guild_stats
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
