import logging
from typing import Any

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.lifecycle.service import wipe_guild_data
from anecbot.shared.views.errors import notify_unexpected_error

logger = logging.getLogger(__name__)


class ResetConfirmView(discord.ui.View):
    """Confirmation buttons for guild data reset."""

    def __init__(self, guild_id: int):
        """Store the target guild id for the confirm/cancel callbacks."""
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(
        label="Confirmer la suppression", style=discord.ButtonStyle.danger
    )
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Wipe all guild data."""
        db = get_db(interaction)
        await wipe_guild_data(db, self.guild_id)

        await interaction.response.edit_message(
            content="✅ Toutes les données ont été supprimées. Tu peux reconfigurer le bot.",
            view=None,
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the reset."""
        await interaction.response.edit_message(
            content="❌ Suppression annulée.",
            view=None,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during data reset."""
        await notify_unexpected_error(interaction, error, logger)


async def handle(interaction: discord.Interaction):
    """Reset all data for this guild with confirmation."""
    assert interaction.guild_id is not None
    view = ResetConfirmView(interaction.guild_id)
    await interaction.response.send_message(
        "⚠️ **Attention !** Cette action va supprimer :\n"
        "- Tous les joueurs inscrits\n"
        "- Toutes les anecdotes\n"
        "- Tous les votes\n"
        "- Le leaderboard\n\n"
        "Cette action est **irréversible**.",
        view=view,
        ephemeral=True,
    )
