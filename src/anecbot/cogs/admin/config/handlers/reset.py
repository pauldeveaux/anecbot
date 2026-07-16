import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.enums import LeaderboardResetMode
from anecbot.models.guild import Guild


class ConfigResetView(discord.ui.View):
    """Confirmation buttons for config reset."""

    def __init__(self, guild_id: int):
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Reset config to defaults."""
        db = get_db(interaction)
        await Guild.upsert(
            db,
            self.guild_id,
            channel_id=None,
            interval_days=1,
            publish_time="15:00",
            days_off="",
            reveal_interval_days=1,
            reveal_time="13:30",
            leaderboard_reset_mode=LeaderboardResetMode.NEVER,
            leaderboard_reset_interval=1,
            leaderboard_reset_anchor=None,
            daily_limit=0,
        )
        await interaction.response.edit_message(
            content="✅ Configuration réinitialisée aux valeurs par défaut.",
            view=None,
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the reset."""
        await interaction.response.edit_message(
            content="❌ Réinitialisation annulée.",
            view=None,
        )


async def handle(interaction: discord.Interaction):
    """Reset guild configuration with confirmation."""
    assert interaction.guild_id is not None
    view = ConfigResetView(interaction.guild_id)
    await interaction.response.send_message(
        "⚠️ Réinitialiser toute la configuration aux valeurs par défaut ?",
        view=view,
        ephemeral=True,
    )
