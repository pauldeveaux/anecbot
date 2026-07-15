import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.config.leaderboard_reset_format import (
    format_leaderboard_reset_anchor,
    format_leaderboard_reset_interval,
)
from anecbot.cogs.admin.config.leaderboard_reset_mode import (
    MODE_LABELS as LEADERBOARD_RESET_MODE_LABELS,
)
from anecbot.cogs.admin.config.reveal_mode import MODE_LABELS as REVEAL_MODE_LABELS
from anecbot.models.enums import LeaderboardResetMode
from anecbot.models.guild import Guild


def build_config_embed(
    guild: Guild, channel: discord.abc.GuildChannel | None
) -> discord.Embed:
    """Build an embed showing the full current guild configuration."""
    days_off = guild.days_off if guild.days_off else "aucun"
    leaderboard_reset = format_leaderboard_reset_interval(
        guild.leaderboard_reset_mode, guild.leaderboard_reset_interval
    )
    daily_limit = str(guild.daily_limit) if guild.daily_limit else "illimitée"

    embed = discord.Embed(
        title="Configuration actuelle",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="Channel",
        value=channel.mention if channel else str(guild.channel_id),
        inline=True,
    )
    embed.add_field(
        name="Intervalle",
        value=f"{guild.interval_days} jour(s) actif(s)",
        inline=True,
    )
    embed.add_field(name="Heure de publication", value=guild.publish_time, inline=True)
    embed.add_field(name="Jours off", value=days_off, inline=True)
    embed.add_field(
        name="Mode de révélation",
        value=REVEAL_MODE_LABELS[guild.reveal_mode],
        inline=True,
    )
    embed.add_field(
        name="Délai de révélation",
        value=f"{guild.reveal_interval_days} jour(s)",
        inline=True,
    )
    embed.add_field(name="Heure de révélation", value=guild.reveal_time, inline=True)
    embed.add_field(name="Limite quotidienne", value=daily_limit, inline=True)
    embed.add_field(
        name="Fréquence de reset du leaderboard",
        value=LEADERBOARD_RESET_MODE_LABELS[guild.leaderboard_reset_mode],
        inline=True,
    )
    if guild.leaderboard_reset_mode != LeaderboardResetMode.NEVER:
        embed.add_field(
            name="Reset tous les", value=leaderboard_reset, inline=True
        )
        embed.add_field(
            name="Jour de reset",
            value=format_leaderboard_reset_anchor(
                guild.leaderboard_reset_mode, guild.leaderboard_reset_anchor
            ),
            inline=True,
        )
    return embed


async def handle(interaction: discord.Interaction):
    """Show the current guild configuration."""
    assert interaction.guild_id is not None
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id) or Guild(
        guild_id=interaction.guild_id
    )

    channel = None
    if interaction.guild and guild.channel_id:
        channel = interaction.guild.get_channel(guild.channel_id)
    embed = build_config_embed(guild, channel)
    await interaction.response.send_message(embed=embed, ephemeral=True)
