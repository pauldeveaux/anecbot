import logging

import discord

from anecbot.features.player.service import MAX_TARGETS
from anecbot.features.vote.service import record_vote
from anecbot.models.enums import VoteResult

logger = logging.getLogger(__name__)


class McqView(discord.ui.View):
    """MCQ select menu for guessing who/what an anecdote is about."""

    def __init__(self, anecdote_id: int, options: list[tuple[str, int]]):
        """Build the select menu from (label, value) pairs, capped to Discord's 25-option limit."""
        super().__init__(timeout=None)
        self.anecdote_id = anecdote_id
        self._labels = {value: label for label, value in options}
        select_options = [
            discord.SelectOption(label=label, value=str(value))
            for label, value in options[:MAX_TARGETS]
        ]
        self.select = discord.ui.Select(
            custom_id=f"mcq-vote:{anecdote_id}",
            placeholder="Devine à qui appartient cette anecdote...",
            options=select_options,
        )
        self.select.callback = self._on_vote
        self.add_item(self.select)

    async def _on_vote(self, interaction: discord.Interaction):
        """Record the vote, confirm the guess, and DM a reminder with a link to the message."""
        voted_value = int(self.select.values[0])
        db = interaction.client.db  # type: ignore[attr-defined]
        result = await record_vote(
            db, self.anecdote_id, interaction.user.id, voted_value
        )

        if result == VoteResult.CLOSED:
            await interaction.response.send_message(
                "❌ Le vote pour cette anecdote est clos.", ephemeral=True
            )
            return

        if result == VoteResult.IS_AUTHOR:
            await interaction.response.send_message(
                "❌ Tu ne peux pas voter sur ta propre anecdote.", ephemeral=True
            )
            return

        guessed_name = self._labels.get(voted_value, str(voted_value))

        await interaction.response.send_message(
            f"✅ Vote enregistré : **{guessed_name}**", ephemeral=True
        )

        if interaction.message is not None:
            try:
                await interaction.user.send(
                    f"🗳️ Tu as voté pour **{guessed_name}** sur cette anecdote : "
                    f"{interaction.message.jump_url}"
                )
            except discord.Forbidden:
                logger.debug("Cannot DM user %s (DMs disabled)", interaction.user.id)
