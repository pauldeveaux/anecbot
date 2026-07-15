import discord

from anecbot.features.player.service import (
    get_active_targets,
    get_member_guilds,
    is_active_submitter,
)
from anecbot.models.player import Player
from anecbot.utils.player import display_name


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
        """Handle target selection — open text input modal."""
        target_id = int(self.select.values[0])
        modal = AnecdoteModal(self.guild_id, target_id)
        await interaction.response.send_modal(modal)


class ServerSelectView(discord.ui.View):
    """Select menu to choose the server (DM with multiple guilds)."""

    def __init__(self, guilds: list[tuple[int, str]]):
        super().__init__(timeout=120)
        options = [
            discord.SelectOption(label=name, value=str(gid)) for gid, name in guilds
        ]
        self.select = discord.ui.Select(
            placeholder="Choisis le serveur",
            options=options,
        )
        self.select.callback = self._on_select
        self.add_item(self.select)

    async def _on_select(self, interaction: discord.Interaction):
        """Handle server selection — check submitter status, then show target select."""
        guild_id = int(self.select.values[0])
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
    """Modal for anecdote text input — placeholder for ANEC-14."""

    content = discord.ui.TextInput(
        label="Ton anecdote",
        style=discord.TextStyle.paragraph,
        placeholder="Écris ton anecdote ici...",
        max_length=2000,
    )

    def __init__(self, guild_id: int, target_id: int):
        super().__init__()
        self.guild_id = guild_id
        self.target_id = target_id

    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submit — save logic in ANEC-14."""
        await interaction.response.send_message(
            "🚧 Soumission en cours de développement (ANEC-14).",
            ephemeral=True,
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

    view = ServerSelectView(guilds)
    await interaction.response.send_message(
        "Choisis le serveur :",
        view=view,
        ephemeral=True,
    )
