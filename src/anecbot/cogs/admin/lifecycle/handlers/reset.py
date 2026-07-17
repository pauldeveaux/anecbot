import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild

logger = logging.getLogger(__name__)


class ResetConfirmView(discord.ui.View):
    """Confirmation buttons for guild data reset."""

    def __init__(self, guild_id: int):
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
        await db.execute(
            "DELETE FROM votes WHERE anecdote_id IN (SELECT id FROM anecdotes WHERE guild_id = ?)",
            (self.guild_id,),
        )
        await db.execute("DELETE FROM anecdotes WHERE guild_id = ?", (self.guild_id,))
        await db.execute("DELETE FROM leaderboard WHERE guild_id = ?", (self.guild_id,))
        await db.execute("DELETE FROM players WHERE guild_id = ?", (self.guild_id,))
        await Guild.upsert(db, self.guild_id, started=0, started_at=None)
        await db.commit()
        logger.warning("All data wiped for guild %s", self.guild_id)

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
