import discord

from anecbot.models.player import Player
from anecbot.utils.player import display_name


class McqView(discord.ui.View):
    """MCQ select menu for guessing who an anecdote is about."""

    def __init__(self, anecdote_id: int, targets: list[Player], guild: discord.Guild):
        super().__init__(timeout=None)
        self.anecdote_id = anecdote_id
        options = [
            discord.SelectOption(label=display_name(t, guild), value=str(t.user_id))
            for t in targets[:25]
        ]
        self.select = discord.ui.Select(
            placeholder="Devine à qui appartient cette anecdote...",
            options=options,
        )
        self.select.callback = self._on_vote
        self.add_item(self.select)

    async def _on_vote(self, interaction: discord.Interaction):
        """Handle a vote — recording lands in ANEC-18."""
        await interaction.response.send_message(
            "🚧 Vote en cours de développement (ANEC-18).", ephemeral=True
        )
