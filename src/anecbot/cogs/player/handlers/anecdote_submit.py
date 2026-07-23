import asyncio
import logging
from typing import Any, cast

import discord

from anecbot.features.anecdote.service import create_anecdote, daily_limit_status
from anecbot.features.player.service import (
    get_active_targets,
    get_member_guilds,
    is_active_submitter,
)
from anecbot.models.anecdote_media import AnecdoteMedia
from anecbot.models.player import Player
from anecbot.shared.views.errors import notify_unexpected_error
from anecbot.shared.views.guild_select import GuildSelectView
from anecbot.utils.player import display_name
from anecbot.utils.text import with_blank_lines

logger = logging.getLogger(__name__)

MIN_CHOICES = 1
MAX_CHOICES = 10
MAX_MEDIA = 1
_MEDIA_TIMEOUT_SECONDS = 180


def _is_image_attachment(attachment: discord.Attachment) -> bool:
    """Return whether an attachment looks like an image, by content type or extension."""
    if attachment.content_type and attachment.content_type.startswith("image/"):
        return True
    return attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))


class _MediaCollectView(discord.ui.View):
    """Attached while collecting media — its button is the only way to stop collecting."""

    def __init__(self):
        """Never auto-time-out — the collection loop itself handles message-inactivity timeout."""
        super().__init__(timeout=None)
        self.stopped = asyncio.Event()

    @discord.ui.button(label="✅ Terminé", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Signal the collection loop to stop; it shows the confirm step next."""
        self.stopped.set()
        await interaction.response.defer()


async def _run_media_collection(
    interaction: discord.Interaction,
) -> list[AnecdoteMedia]:
    """Show the collection prompt and gather one image attachment from a follow-up DM message.

    Modals can't carry file uploads, so this runs as a message wait in the same DM channel after
    the user opted in. Stops once the one allowed image is collected, the Terminé button is
    clicked, or a period of inactivity passes — never blocks the submission either way. The
    Terminé button is re-attached to the "not understood" retry reply too, so it stays visible
    without scrolling back up.
    """
    collect_view = _MediaCollectView()
    await interaction.response.edit_message(
        content=(
            "📎 Envoie une image en pièce jointe.\n"
            "Clique sur ✅ Terminé si tu ne veux pas en ajouter."
        ),
        embed=None,
        view=collect_view,
    )
    channel = interaction.channel
    assert channel is not None
    sendable = cast("discord.abc.Messageable", channel)
    media: list[AnecdoteMedia] = []

    def check(message: discord.Message) -> bool:
        """Match only messages from the submitter, in this same DM channel."""
        return (
            message.channel.id == channel.id
            and message.author.id == interaction.user.id
        )

    stop_wait = asyncio.ensure_future(collect_view.stopped.wait())
    while len(media) < MAX_MEDIA:
        if collect_view.stopped.is_set():
            break

        message_wait = asyncio.ensure_future(
            interaction.client.wait_for("message", check=check)
        )
        done, _pending = await asyncio.wait(
            {message_wait, stop_wait},
            timeout=_MEDIA_TIMEOUT_SECONDS,
            return_when=asyncio.FIRST_COMPLETED,
        )
        if message_wait not in done:
            message_wait.cancel()
            break
        message = message_wait.result()

        added = 0
        for index, attachment in enumerate(message.attachments):
            if len(media) >= MAX_MEDIA:
                break
            if not _is_image_attachment(attachment):
                continue
            media.append(
                AnecdoteMedia(
                    media_url=attachment.url,
                    dm_channel_id=message.channel.id,
                    dm_message_id=message.id,
                    attachment_index=index,
                )
            )
            added += 1

        if not added:
            await sendable.send(
                "❌ Je n'ai pas compris — envoie une image en pièce jointe, "
                "ou clique sur ✅ Terminé.",
                view=collect_view,
            )
            continue

        await sendable.send("✅ Image ajoutée !")

    stop_wait.cancel()
    collect_view.stop()
    return media


class _MediaOptInView(discord.ui.View):
    """Ask whether to attach an image, before showing the confirmation step either way."""

    def __init__(
        self,
        guild_id: int,
        guild_name: str,
        content: str,
        target_label: str,
        choice_labels: list[str],
    ):
        """Store everything needed to build the confirm step once media is decided."""
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.guild_name = guild_name
        self.content = content
        self.target_label = target_label
        self.choice_labels = choice_labels

    @discord.ui.button(label="📎 Ajouter une image", style=discord.ButtonStyle.primary)
    async def add_media(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Collect one image via a follow-up DM step, then send the confirm step below it.

        The confirm step is a new message, not an edit of the (now scrolled-up) collection
        prompt, so it lands right after whatever the user just sent instead of requiring a
        scroll back up to find the Confirmer/Annuler buttons.
        """
        media = await _run_media_collection(interaction)
        image_url = media[0].media_url if media else None
        embed = _build_confirm_embed(
            self.content,
            self.guild_name,
            self.target_label,
            self.choice_labels,
            image_url,
        )
        view = ConfirmSubmitView(
            self.guild_id, self.content, self.target_label, self.choice_labels, media
        )
        await interaction.edit_original_response(
            content="📎 Étape médias terminée.", embed=None, view=None
        )
        sendable = cast("discord.abc.Messageable", interaction.channel)
        await sendable.send(embed=embed, view=view)

    @discord.ui.button(label="➡️ Passer", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Move directly to the confirm step with no media."""
        embed = _build_confirm_embed(
            self.content, self.guild_name, self.target_label, self.choice_labels, None
        )
        view = ConfirmSubmitView(
            self.guild_id, self.content, self.target_label, self.choice_labels, []
        )
        await interaction.response.edit_message(content=None, embed=embed, view=view)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during the media opt-in step."""
        await notify_unexpected_error(interaction, error, logger)


class TargetSelectView(discord.ui.View):
    """Select menu to choose the anecdote's roster target."""

    def __init__(self, guild_id: int, targets: list[Player], guild: discord.Guild):
        """Build the target select menu, capped to Discord's 25-option limit."""
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.guild = guild
        self.targets = targets[:25]
        options = [
            discord.SelectOption(
                label=display_name(t, guild),
                value=str(t.user_id),
            )
            for t in self.targets
        ]
        self.select = discord.ui.Select(
            placeholder="Choisis la cible de ton anecdote",
            options=options,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        """Open the anecdote text modal, with the other active targets as MCQ wrong choices."""
        target_id = int(self.select.values[0])
        target_label = None
        choice_labels = []
        for t in self.targets:
            label = display_name(t, self.guild)
            if t.user_id == target_id:
                target_label = label
            else:
                choice_labels.append(label)
        assert target_label is not None
        modal = AnecdoteModal(
            self.guild_id,
            self.guild,
            target_label=target_label,
            choice_labels=choice_labels,
        )
        await interaction.response.send_modal(modal)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during target selection."""
        await notify_unexpected_error(interaction, error, logger)


class TargetModeView(discord.ui.View):
    """Choose between a roster target (existing player) or a custom free-text target."""

    def __init__(self, guild_id: int, targets: list[Player], guild: discord.Guild):
        """Store the guild's active targets, used if the roster mode is picked."""
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.targets = targets
        self.guild = guild

    @discord.ui.button(label="🎯 Cible du serveur", style=discord.ButtonStyle.primary)
    async def roster(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the roster target select menu."""
        if not self.targets:
            await interaction.response.edit_message(
                content=f"❌ Aucune cible disponible sur **{self.guild.name}**.",
                view=None,
            )
            return
        await interaction.response.edit_message(
            content="Choisis la cible de ton anecdote :",
            view=TargetSelectView(self.guild_id, self.targets, self.guild),
        )

    @discord.ui.button(
        label="✏️ Cible personnalisée", style=discord.ButtonStyle.secondary
    )
    async def custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the modal to write the anecdote and name a custom (non-roster) target."""
        modal = CustomAnecdoteModal(self.guild_id, self.guild)
        await interaction.response.send_modal(modal)

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during mode selection."""
        await notify_unexpected_error(interaction, error, logger)


async def _on_guild_selected(interaction: discord.Interaction, guild_id: int) -> None:
    """Handle server selection — check submit permission and daily limit, then show mode choice."""
    await _show_mode_choice(interaction, guild_id, edit=True)


async def _show_mode_choice(
    interaction: discord.Interaction, guild_id: int, edit: bool
) -> None:
    """Check submit permission and the daily limit for the guild, then show the target-mode choice."""
    db = interaction.client.db  # type: ignore[attr-defined]
    guild = interaction.client.get_guild(guild_id)
    assert guild is not None
    user_id = interaction.user.id

    if not await is_active_submitter(db, guild_id, user_id):
        content = f"❌ Tu n'es pas inscrit(e) comme rédacteur sur **{guild.name}**."
        view = None
    else:
        reached, limit = await daily_limit_status(db, guild_id, user_id)
        if reached:
            content = (
                f"❌ Tu as atteint la limite quotidienne de {limit} "
                f"soumission(s) sur **{guild.name}**."
            )
            view = None
        else:
            targets = await get_active_targets(db, guild_id)
            content = "Choisis comment définir la cible de ton anecdote :"
            view = TargetModeView(guild_id, targets, guild)

    if edit:
        await interaction.response.edit_message(content=content, view=view)
    else:
        await interaction.response.send_message(
            content, view=view or discord.utils.MISSING, ephemeral=True
        )


class CustomAnecdoteModal(discord.ui.Modal, title="Soumettre une anecdote"):
    """Modal to write the anecdote and name its custom (non-roster) target, in that order."""

    content = discord.ui.TextInput(
        label="Ton anecdote",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )
    target_name = discord.ui.TextInput(
        label="Nom de la cible",
        max_length=100,
    )

    def __init__(self, guild_id: int, guild: discord.Guild):
        """Store the guild for the anecdote and custom target being submitted."""
        super().__init__()
        self.guild_id = guild_id
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        """Show the choice-builder view, seeded with the anecdote and target, no choices yet."""
        view = ChoiceBuilderView(
            self.guild_id, self.guild, str(self.content), str(self.target_name)
        )
        await interaction.response.edit_message(
            content=None, embed=view.build_embed(), view=view
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        """Log and notify the user on an unexpected error while submitting the anecdote."""
        await notify_unexpected_error(interaction, error, logger)


class ChoiceBuilderView(discord.ui.View):
    """Build the list of wrong choices for a custom target, one at a time."""

    def __init__(
        self, guild_id: int, guild: discord.Guild, content: str, target_label: str
    ):
        """Store the guild, the anecdote content, the named target, and an empty choice list."""
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.guild = guild
        self.content = content
        self.target_label = target_label
        self.choices: list[str] = []
        self.sync_buttons()

    def sync_buttons(self) -> None:
        """Enable/disable buttons based on the current choice count."""
        self.add_choice.disabled = len(self.choices) >= MAX_CHOICES
        self.remove_choice.disabled = not self.choices
        self.finish.disabled = len(self.choices) < MIN_CHOICES

    def build_embed(self) -> discord.Embed:
        """Build the embed showing the target and choices collected so far."""
        embed = discord.Embed(title="Cible personnalisée", color=discord.Color.blue())
        embed.add_field(name="Cible", value=self.target_label, inline=False)
        choices_value = (
            "\n".join(f"- {c}" for c in self.choices)
            if self.choices
            else "Aucun choix ajouté pour l'instant."
        )
        embed.add_field(
            name=f"Autres choix ({len(self.choices)}/{MAX_CHOICES})",
            value=choices_value,
            inline=False,
        )
        return embed

    @discord.ui.button(label="➕ Ajouter un choix", style=discord.ButtonStyle.primary)
    async def add_choice(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Open the modal to add one more wrong choice."""
        await interaction.response.send_modal(AddChoiceModal(self))

    @discord.ui.button(
        label="➖ Retirer le dernier", style=discord.ButtonStyle.secondary
    )
    async def remove_choice(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Remove the most recently added wrong choice."""
        if self.choices:
            self.choices.pop()
        self.sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="✅ Terminer", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show the media opt-in step, before the confirmation step."""
        choice_labels = list(self.choices)
        view = _MediaOptInView(
            self.guild_id,
            self.guild.name,
            self.content,
            self.target_label,
            choice_labels,
        )
        await interaction.response.edit_message(
            content="Veux-tu ajouter une image à ton anecdote ?",
            embed=None,
            view=view,
        )

    @discord.ui.button(label="❌ Annuler", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Discard the submission."""
        await interaction.response.edit_message(
            content="❌ Soumission annulée.", embed=None, view=None
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error while building choices."""
        await notify_unexpected_error(interaction, error, logger)


class AddChoiceModal(discord.ui.Modal, title="Ajouter un choix"):
    """Modal to add one wrong choice to a custom target's choice list."""

    choice_label = discord.ui.TextInput(
        label="Autre choix",
        max_length=100,
    )

    def __init__(self, builder_view: ChoiceBuilderView):
        """Store the builder view to append the new choice to."""
        super().__init__()
        self.builder_view = builder_view

    async def on_submit(self, interaction: discord.Interaction):
        """Append the choice, rejecting a duplicate of the target or an existing choice."""
        label = str(self.choice_label).strip()
        existing = {self.builder_view.target_label.strip().casefold()} | {
            c.strip().casefold() for c in self.builder_view.choices
        }
        if label.casefold() in existing:
            await interaction.response.send_message(
                "❌ Ce choix existe déjà (identique à la cible ou à un autre choix).",
                ephemeral=True,
            )
            return

        self.builder_view.choices.append(label)
        self.builder_view.sync_buttons()
        await interaction.response.edit_message(
            embed=self.builder_view.build_embed(), view=self.builder_view
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        """Log and notify the user on an unexpected error while adding a choice."""
        await notify_unexpected_error(interaction, error, logger)


def _build_confirm_embed(
    content: str,
    guild_name: str,
    target_label: str,
    choice_labels: list[str],
    image_url: str | None,
) -> discord.Embed:
    """Build the embed confirming an anecdote's content, target, MCQ choices, and image."""
    embed = discord.Embed(
        title="Confirme ta soumission", description=with_blank_lines(content)
    )
    embed.add_field(name="Cible", value=target_label, inline=True)
    if choice_labels:
        embed.add_field(
            name="Autres choix du QCM",
            value="\n".join(f"- {c}" for c in choice_labels),
            inline=False,
        )
    embed.add_field(name="Serveur", value=guild_name, inline=True)
    if image_url is not None:
        embed.set_image(url=image_url)
    return embed


class AnecdoteModal(discord.ui.Modal, title="Soumettre une anecdote"):
    """Modal for anecdote text input."""

    content = discord.ui.TextInput(
        label="Ton anecdote",
        style=discord.TextStyle.paragraph,
        max_length=2000,
    )

    def __init__(
        self,
        guild_id: int,
        guild: discord.Guild,
        *,
        target_label: str,
        choice_labels: list[str],
    ):
        """Store the guild and the anecdote's target/MCQ wrong choices."""
        super().__init__()
        self.guild_id = guild_id
        self.guild = guild
        self.target_label = target_label
        self.choice_labels = choice_labels

    async def on_submit(self, interaction: discord.Interaction):
        """Show the media opt-in step, before the confirmation step."""
        text = str(self.content)
        view = _MediaOptInView(
            self.guild_id, self.guild.name, text, self.target_label, self.choice_labels
        )
        await interaction.response.edit_message(
            content="Veux-tu ajouter une image à ton anecdote ?",
            embed=None,
            view=view,
        )

    async def on_error(
        self, interaction: discord.Interaction, error: Exception, /
    ) -> None:
        """Log and notify the user on an unexpected error during anecdote submission."""
        await notify_unexpected_error(interaction, error, logger)


class ConfirmSubmitView(discord.ui.View):
    """Confirm or cancel a pending anecdote submission."""

    def __init__(
        self,
        guild_id: int,
        content: str,
        target_label: str,
        choice_labels: list[str],
        media: list[AnecdoteMedia],
    ):
        """Store the pending anecdote's guild, content, target, MCQ wrong choices, and media."""
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.content = content
        self.target_label = target_label
        self.choice_labels = choice_labels
        self.media = media

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Save the anecdote as PENDING."""
        db = interaction.client.db  # type: ignore[attr-defined]
        await create_anecdote(
            db,
            self.guild_id,
            interaction.user.id,
            self.content,
            target_label=self.target_label,
            choice_labels=self.choice_labels,
            media=self.media,
        )
        await interaction.response.edit_message(
            content="✅ Ton anecdote a été soumise.", embed=None, view=None
        )

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Discard the anecdote without saving."""
        await interaction.response.edit_message(
            content="❌ Soumission annulée.", embed=None, view=None
        )

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        """Log and notify the user on an unexpected error during confirmation."""
        await notify_unexpected_error(interaction, error, logger)


async def handle(interaction: discord.Interaction):
    """Start the anecdote submission flow."""
    guilds = get_member_guilds(interaction.client, interaction.user.id)

    if not guilds:
        await interaction.response.send_message(
            "❌ Le bot n'est présent sur aucun serveur avec toi.",
            ephemeral=True,
        )
        return

    if len(guilds) == 1:
        guild_id, _ = guilds[0]
        await _show_mode_choice(interaction, guild_id, edit=False)
        return

    view = GuildSelectView(guilds, _on_guild_selected)
    await interaction.response.send_message(
        "Choisis le serveur :",
        view=view,
        ephemeral=True,
    )
