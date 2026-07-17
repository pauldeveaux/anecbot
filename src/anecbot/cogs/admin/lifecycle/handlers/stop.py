import logging
from typing import Any

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild
from anecbot.shared.views.errors import notify_unexpected_error

logger = logging.getLogger(__name__)


class StopConfirmView(discord.ui.View):
    """Confirmation button for stopping the game."""

    def __init__(self, guild_id: int):
        """Store the target guild id for the confirm/cancel callbacks."""
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="Mettre en pause", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Stop the game."""
        db = get_db(interaction)
        await Guild.upsert(db, self.guild_id, started=0)
        logger.info("Game stopped for guild %s", self.guild_id)
        await interaction.response.edit_message(
            content="✅ Jeu mis en pause. Les publications sont arrêtées.",
            view=None,
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel stop."""
        await interaction.response.edit_message(
            content="❌ Mise en pause annulée.",
            view=None,
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error while stopping the game."""
        await notify_unexpected_error(interaction, error, logger)


async def handle(interaction: discord.Interaction):
    """Stop the quiz game for this guild."""
    db = get_db(interaction)
    guild = await Guild.get(db, interaction.guild_id)

    if guild is None or not guild.started:
        await interaction.response.send_message(
            "ℹ️ Le jeu n'est pas en cours.",
            ephemeral=True,
        )
        return

    assert interaction.guild_id is not None
    view = StopConfirmView(interaction.guild_id)
    await interaction.response.send_message(
        "⚠️ Mettre le jeu en pause ? Les publications seront arrêtées.",
        view=view,
        ephemeral=True,
    )
