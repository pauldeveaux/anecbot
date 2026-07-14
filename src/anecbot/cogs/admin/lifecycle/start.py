import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild


def _build_config_embed(guild: Guild, channel) -> discord.Embed:
    """Build an embed showing the current guild configuration."""
    days_off = guild.days_off if guild.days_off else "aucun"
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
        name="Délai de révélation",
        value=f"{guild.reveal_interval_days} jour(s)",
        inline=True,
    )
    embed.add_field(name="Heure de révélation", value=guild.reveal_time, inline=True)
    return embed


class StartConfirmView(discord.ui.View):
    """Confirmation button for starting the game."""

    def __init__(self, guild_id: int):
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="Démarrer", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Start the game."""
        db = get_db(interaction)
        await Guild.upsert(db, self.guild_id, started=1)
        await interaction.response.edit_message(
            content="✅ Jeu démarré ! Les publications commenceront selon la configuration.",
            view=None,
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel start."""
        await interaction.response.edit_message(
            content="❌ Démarrage annulé.",
            view=None,
        )


async def handle(interaction: discord.Interaction):
    """Start the quiz game for this guild."""
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id)

    if guild is None or guild.channel_id is None:
        await interaction.response.send_message(
            "❌ Configure d'abord un channel avec `/config channel`.",
            ephemeral=True,
        )
        return

    if guild.started:
        await interaction.response.send_message(
            "ℹ️ Le jeu est déjà en cours.",
            ephemeral=True,
        )
        return

    channel = (
        interaction.guild.get_channel(guild.channel_id) if interaction.guild else None
    )  # type: ignore[union-attr]
    embed = _build_config_embed(guild, channel)
    view = StartConfirmView(interaction.guild_id)  # type: ignore[arg-type]

    await interaction.response.send_message(
        "Démarrer le jeu avec cette configuration ?",
        embed=embed,
        view=view,
        ephemeral=True,
    )
