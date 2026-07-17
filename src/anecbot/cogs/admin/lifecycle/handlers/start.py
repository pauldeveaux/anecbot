import logging
from typing import Any

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.config.handlers.show import build_config_embed
from anecbot.features.lifecycle.service import start_game
from anecbot.models.guild import Guild
from anecbot.shared.views.errors import notify_unexpected_error

logger = logging.getLogger(__name__)


class StartConfirmView(discord.ui.View):
    """Confirmation button for starting the game."""

    def __init__(self, guild_id: int):
        """Store the target guild id for the confirm/cancel callbacks."""
        super().__init__(timeout=30)
        self.guild_id = guild_id

    @discord.ui.button(label="Démarrer", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Start the game and announce it publicly."""
        db = get_db(interaction)
        await start_game(interaction.client, db, self.guild_id)
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

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error while starting the game."""
        await notify_unexpected_error(interaction, error, logger)


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
    embed = build_config_embed(guild, channel)
    view = StartConfirmView(interaction.guild_id)  # type: ignore[arg-type]

    await interaction.response.send_message(
        "Démarrer le jeu avec cette configuration ?",
        embed=embed,
        view=view,
        ephemeral=True,
    )
