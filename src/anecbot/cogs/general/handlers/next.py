import discord

from anecbot.features.next.service import NextEvents, get_next_events
from anecbot.utils.time import discord_timestamp_full_relative as ts, utcnow


def build_next_embed(events: NextEvents) -> discord.Embed:
    """Build a public embed with upcoming scheduled events."""
    embed = discord.Embed(
        title="Prochains événements",
        color=discord.Color.blue(),
    )

    if events.next_publication is None:
        embed.description = "Le jeu n'est pas en cours."
        return embed

    pub_value = ts(events.next_publication)
    if events.pending_anecdotes == 0:
        pub_value += "\n\n⚠️ Aucune anecdote en attente !"
    else:
        pub_value += f"\n\n{events.pending_anecdotes} anecdote(s) en attente"

    embed.add_field(
        name="\U0001f4e2 Prochaine publication",
        value=pub_value,
        inline=True,
    )

    if events.next_reveal:
        reveal_value = ts(events.next_reveal)
    else:
        reveal_value = "Aucune révélation en attente"

    embed.add_field(
        name="\U0001f50d Prochaine révélation",
        value=reveal_value,
        inline=True,
    )

    if not events.leaderboard_reset_hidden:
        if events.leaderboard_reset_placeholder:
            reset_value = "À venir"
        elif events.next_leaderboard_reset:
            reset_value = ts(events.next_leaderboard_reset)
        else:
            reset_value = "—"

        embed.add_field(
            name="\U0001f504 Prochain reset du leaderboard",
            value=reset_value,
            inline=True,
        )

    return embed


async def handle(interaction: discord.Interaction):
    """Show upcoming scheduled events for this guild."""
    assert interaction.guild_id is not None
    db = interaction.client.db  # type: ignore[attr-defined]
    now = utcnow()
    events = await get_next_events(db, interaction.guild_id, now)
    embed = build_next_embed(events)
    await interaction.response.send_message(embed=embed)
