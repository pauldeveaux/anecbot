import logging

import discord

from anecbot.features.player.service import MAX_TARGETS
from anecbot.features.vote.service import record_vote
from anecbot.models.enums import VoteResult
from anecbot.models.player import Player
from anecbot.utils.player import display_name

logger = logging.getLogger(__name__)


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
        """Record the vote, confirm the guess, and DM a reminder with a link to the message."""
        target_id = int(self.select.values[0])
        db = interaction.client.db  # type: ignore[attr-defined]
        result = await record_vote(db, self.anecdote_id, interaction.user.id, target_id)

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

        assert interaction.guild_id is not None
        guessed = await Player.get(db, interaction.guild_id, target_id)
        guessed_name = (
            display_name(guessed, interaction.guild) if guessed else str(target_id)
        )

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
