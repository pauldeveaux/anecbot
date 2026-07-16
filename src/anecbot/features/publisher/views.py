import discord

from anecbot.features.player.service import MAX_TARGETS
from anecbot.features.vote.service import record_vote
from anecbot.models.enums import VoteResult
from anecbot.models.player import Player
from anecbot.utils.player import display_name


class McqView(discord.ui.View):
    """MCQ select menu for guessing who an anecdote is about."""

    def __init__(self, anecdote_id: int, targets: list[Player], guild: discord.Guild):
        super().__init__(timeout=None)
        self.anecdote_id = anecdote_id
        options = [
            discord.SelectOption(label=display_name(t, guild), value=str(t.user_id))
            for t in targets[:MAX_TARGETS]
        ]
        self.select = discord.ui.Select(
            placeholder="Devine à qui appartient cette anecdote...",
            options=options,
        )
        self.select.callback = self._on_vote
        self.add_item(self.select)

    async def _on_vote(self, interaction: discord.Interaction):
        """Record the vote and acknowledge, or reject if voting has closed."""
        target_id = int(self.select.values[0])
        db = interaction.client.db  # type: ignore[attr-defined]
        result = await record_vote(db, self.anecdote_id, interaction.user.id, target_id)

        if result == VoteResult.CLOSED:
            await interaction.response.send_message(
                "❌ Le vote pour cette anecdote est clos.", ephemeral=True
            )
            return

        await interaction.response.send_message("✅ Vote enregistré !", ephemeral=True)
