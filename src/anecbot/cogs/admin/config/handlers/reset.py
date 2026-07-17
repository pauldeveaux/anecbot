import logging
from typing import Any

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.config.service import reset_guild_config
from anecbot.models.guild import Guild
from anecbot.shared.views.errors import notify_unexpected_error

logger = logging.getLogger(__name__)


class ConfigResetView(discord.ui.View):
    """Confirmation buttons for config reset."""

    def __init__(self, guild_id: int):
        """Store the target guild id for the confirm/cancel callbacks."""
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Reset config to defaults and stop the game (a reset channel can't stay started)."""
        db = get_db(interaction)
        await reset_guild_config(db, self.guild_id)
        logger.info("Config reset to defaults for guild %s", self.guild_id)
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

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during config reset."""
        await notify_unexpected_error(interaction, error, logger)


async def handle(interaction: discord.Interaction):
    """Reset guild configuration with confirmation."""
    assert interaction.guild_id is not None
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id)

    message = "⚠️ Réinitialiser toute la configuration aux valeurs par défaut ?"
    if guild is not None and guild.started:
        message += "\n⚠️ Le jeu est actuellement en cours : il sera aussi mis en pause."

    view = ConfigResetView(interaction.guild_id)
    await interaction.response.send_message(message, view=view, ephemeral=True)
