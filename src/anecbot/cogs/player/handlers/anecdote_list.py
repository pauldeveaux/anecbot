import logging
from typing import Any

import discord

from anecbot.features.anecdote.service import (
    delete_anecdote,
    get_correct_choice,
    get_owned_pending_anecdote,
    get_pending_by_author,
    update_content,
)
from anecbot.features.player.service import get_member_guilds
from anecbot.features.selector.service import compute_selection_probabilities
from anecbot.models.anecdote import Anecdote
from anecbot.shared.views.errors import notify_unexpected_error
from anecbot.shared.views.guild_select import GuildSelectView
from anecbot.shared.views.paginator import NavigablePagesView
from anecbot.utils.text import with_blank_lines
from anecbot.utils.time import discord_timestamp, utcnow

logger = logging.getLogger(__name__)


class EditModal(discord.ui.Modal, title="Modifier ton anecdote"):
    """Modal to edit a PENDING anecdote's content."""

    content = discord.ui.TextInput(
        label="Ton anecdote",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )

    def __init__(self, anecdote_id: int, current_content: str):
        """Pre-fill the text input with the anecdote's current content."""
        super().__init__()
        self.anecdote_id = anecdote_id
        self.content.default = current_content

    async def on_submit(self, interaction: discord.Interaction):
        """Save the edited content, if the anecdote is still PENDING."""
        db = interaction.client.db  # type: ignore[attr-defined]
        anecdote = await get_owned_pending_anecdote(
            db, self.anecdote_id, interaction.user.id
        )
        if anecdote is None:
            await interaction.response.send_message(
                "❌ Cette anecdote n'est plus modifiable (déjà publiée ou supprimée).",
                ephemeral=True,
            )
            return
        await update_content(db, self.anecdote_id, str(self.content))
        await interaction.response.send_message("✅ Anecdote modifiée.", ephemeral=True)

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        """Log and notify the user on an unexpected error during editing."""
        await notify_unexpected_error(interaction, error, logger)


class ConfirmDeleteView(discord.ui.View):
    """Confirm or cancel deleting a PENDING anecdote."""

    def __init__(self, anecdote_id: int):
        """Store the anecdote id targeted by the confirm/cancel callbacks."""
        super().__init__(timeout=120)
        self.anecdote_id = anecdote_id

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Delete the anecdote, if it's still PENDING."""
        db = interaction.client.db  # type: ignore[attr-defined]
        anecdote = await get_owned_pending_anecdote(
            db, self.anecdote_id, interaction.user.id
        )
        if anecdote is None:
            await interaction.response.edit_message(
                content="❌ Cette anecdote n'est plus supprimable (déjà publiée ou supprimée).",
                embed=None,
                view=None,
            )
            return
        await delete_anecdote(db, self.anecdote_id)
        await interaction.response.edit_message(
            content="✅ Anecdote supprimée.", embed=None, view=None
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Discard without deleting."""
        await interaction.response.edit_message(
            content="❌ Suppression annulée.", embed=None, view=None
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during deletion."""
        await notify_unexpected_error(interaction, error, logger)


class AnecdoteBrowserView(NavigablePagesView):
    """Browse PENDING anecdotes one at a time, with Edit/Delete actions on the current one."""

    def __init__(
        self,
        anecdotes: list[Anecdote],
        probabilities: dict[int, float],
        target_labels: dict[int, str],
    ):
        """Store the anecdotes and their display data, one page per anecdote."""
        self.anecdotes = anecdotes
        self.probabilities = probabilities
        self.target_labels = target_labels
        super().__init__(timeout=180)

    @property
    def total_pages(self) -> int:
        """Return the number of anecdotes (one per page)."""
        return len(self.anecdotes)

    @property
    def current(self) -> Anecdote:
        """Return the anecdote currently shown."""
        return self.anecdotes[self.page]

    def _target_field(self, anecdote: Anecdote) -> str:
        """Return the anecdote's target display label."""
        return self.target_labels.get(anecdote.id, "?")

    def build_embed(self) -> discord.Embed:
        """Build the embed for the current anecdote."""
        anecdote = self.current
        embed = discord.Embed(
            title="Anecdotes en attente",
            description=with_blank_lines(anecdote.content),
            color=discord.Color.blue(),
        )
        embed.add_field(name="Cible", value=self._target_field(anecdote), inline=False)
        embed.add_field(
            name="Créée le", value=discord_timestamp(anecdote.created_at), inline=False
        )
        probability = self.probabilities.get(anecdote.id, 0.0)
        embed.add_field(
            name="Probabilité de sélection",
            value=f"~{probability * 100:.1f}%",
            inline=False,
        )
        embed.set_footer(
            text=f"Anecdote {self.page + 1}/{len(self.anecdotes)} — #{anecdote.id} · "
            "Probabilités calculées en temps réel, elles évoluent avec la file."
        )
        return embed

    @discord.ui.button(label="✏️ Modifier", style=discord.ButtonStyle.primary, row=1)
    async def edit_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Open the edit modal for the current anecdote."""
        anecdote = self.current
        modal = EditModal(anecdote.id, anecdote.content)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="🗑️ Supprimer", style=discord.ButtonStyle.danger, row=1)
    async def delete_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Show a delete confirmation for the current anecdote."""
        anecdote = self.current
        embed = discord.Embed(
            title="Confirme la suppression",
            description=with_blank_lines(anecdote.content),
        )
        embed.add_field(name="Cible", value=self._target_field(anecdote), inline=True)
        await interaction.response.edit_message(
            embed=embed, view=ConfirmDeleteView(anecdote.id)
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error while browsing."""
        await notify_unexpected_error(interaction, error, logger)


async def _show_browser(
    interaction: discord.Interaction, guild_id: int, edit: bool
) -> None:
    """Fetch the author's PENDING anecdotes and show the browser, or an empty-state message."""
    db = interaction.client.db  # type: ignore[attr-defined]
    anecdotes = await get_pending_by_author(db, guild_id, interaction.user.id)

    if not anecdotes:
        content = "ℹ️ Aucune anecdote en attente sur ce serveur."
        if edit:
            await interaction.response.edit_message(
                content=content, embed=None, view=None
            )
        else:
            await interaction.response.send_message(content, ephemeral=True)
        return

    # Probabilities are computed over the guild's whole PENDING queue (the draw isn't
    # restricted to this author's own anecdotes), then narrowed down to the ones shown here.
    probabilities = await compute_selection_probabilities(db, guild_id, utcnow())

    target_labels = {
        anecdote.id: (await get_correct_choice(db, anecdote.id)).label
        for anecdote in anecdotes
    }

    view = AnecdoteBrowserView(anecdotes, probabilities, target_labels)
    if edit:
        await interaction.response.edit_message(embed=view.build_embed(), view=view)
    else:
        await interaction.response.send_message(
            embed=view.build_embed(), view=view, ephemeral=True
        )


async def _on_guild_selected(interaction: discord.Interaction, guild_id: int) -> None:
    """Handle server selection — show the anecdote browser."""
    await _show_browser(interaction, guild_id, edit=True)


async def handle(interaction: discord.Interaction):
    """Start the anecdote list flow."""
    guilds = get_member_guilds(interaction.client, interaction.user.id)

    if not guilds:
        await interaction.response.send_message(
            "❌ Le bot n'est présent sur aucun serveur avec toi.",
            ephemeral=True,
        )
        return

    if len(guilds) == 1:
        guild_id, _ = guilds[0]
        await _show_browser(interaction, guild_id, edit=False)
        return

    view = GuildSelectView(guilds, _on_guild_selected)
    await interaction.response.send_message(
        "Choisis le serveur :",
        view=view,
        ephemeral=True,
    )
