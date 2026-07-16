import discord

from anecbot.features.anecdote.service import create_anecdote, daily_limit_status
from anecbot.features.player.service import (
    get_active_targets,
    get_member_guilds,
    is_active_submitter,
)
from anecbot.models.player import Player
from anecbot.shared.views.guild_select import GuildSelectView
from anecbot.utils.player import display_name
from anecbot.utils.text import with_blank_lines


class TargetSelectView(discord.ui.View):
    """Select menu to choose the anecdote target."""

    def __init__(self, guild_id: int, targets: list[Player], guild: discord.Guild):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.guild = guild
        options = [
            discord.SelectOption(
                label=display_name(t, guild),
                value=str(t.user_id),
            )
            for t in targets[:25]
        ]
        self.select = discord.ui.Select(
            placeholder="Choisis la cible de ton anecdote",
            options=options,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        """Handle target selection — check daily limit, then open text input modal."""
        target_id = int(self.select.values[0])
        db = interaction.client.db  # type: ignore[attr-defined]

        reached, limit = await daily_limit_status(
            db, self.guild_id, interaction.user.id
        )
        if reached:
            await interaction.response.edit_message(
                content=(
                    f"❌ Tu as atteint la limite quotidienne de {limit} "
                    f"soumission(s) sur **{self.guild.name}**."
                ),
                view=None,
            )
            return

        modal = AnecdoteModal(self.guild_id, target_id, self.guild)
        await interaction.response.send_modal(modal)


async def _on_guild_selected(interaction: discord.Interaction, guild_id: int) -> None:
    """Handle server selection — check submitter status, then show target select."""
    await _show_targets_or_error(interaction, guild_id, edit=True)


async def _show_targets_or_error(
    interaction: discord.Interaction, guild_id: int, edit: bool
) -> None:
    """Check submit permission for the guild, then show target select or an error."""
    db = interaction.client.db  # type: ignore[attr-defined]
    guild = interaction.client.get_guild(guild_id)
    assert guild is not None
    user_id = interaction.user.id

    if not await is_active_submitter(db, guild_id, user_id):
        content = f"❌ Tu n'es pas inscrit(e) comme rédacteur sur **{guild.name}**."
        view = None
    else:
        targets = await get_active_targets(db, guild_id, exclude_user_id=user_id)
        if not targets:
            content = f"❌ Aucune cible disponible sur **{guild.name}**."
            view = None
        else:
            content = "Choisis la cible de ton anecdote :"
            view = TargetSelectView(guild_id, targets, guild)

    if edit:
        await interaction.response.edit_message(content=content, view=view)
    else:
        await interaction.response.send_message(
            content, view=view or discord.utils.MISSING, ephemeral=True
        )


class AnecdoteModal(discord.ui.Modal, title="Soumettre une anecdote"):
    """Modal for anecdote text input."""

    content = discord.ui.TextInput(
        label="Ton anecdote",
        style=discord.TextStyle.paragraph,
        placeholder="Écris ton anecdote ici...",
        max_length=2000,
    )

    def __init__(self, guild_id: int, target_id: int, guild: discord.Guild):
        super().__init__()
        self.guild_id = guild_id
        self.target_id = target_id
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        """Show a confirmation step before saving the anecdote."""
        db = interaction.client.db  # type: ignore[attr-defined]
        target = await Player.get(db, self.guild_id, self.target_id)
        assert target is not None
        text = str(self.content)

        embed = discord.Embed(
            title="Confirme ta soumission", description=with_blank_lines(text)
        )
        embed.add_field(name="Serveur", value=self.guild.name, inline=True)
        embed.add_field(
            name="Cible", value=display_name(target, self.guild), inline=True
        )

        view = ConfirmSubmitView(self.guild_id, self.target_id, text)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ConfirmSubmitView(discord.ui.View):
    """Confirm or cancel a pending anecdote submission."""

    def __init__(self, guild_id: int, target_id: int, content: str):
        super().__init__(timeout=300)
        self.guild_id = guild_id
        self.target_id = target_id
        self.content = content

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.success)
    async def confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Save the anecdote as PENDING."""
        db = interaction.client.db  # type: ignore[attr-defined]
        await create_anecdote(
            db, self.guild_id, interaction.user.id, self.target_id, self.content
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
        await _show_targets_or_error(interaction, guild_id, edit=False)
        return

    view = GuildSelectView(guilds, _on_guild_selected)
    await interaction.response.send_message(
        "Choisis le serveur :",
        view=view,
        ephemeral=True,
    )
