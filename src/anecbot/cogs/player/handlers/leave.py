import discord

from anecbot.features.player.service import cleanup_if_fully_removed
from anecbot.models.enums import PlayerRole
from anecbot.models.player import Player


class ServerSelectView(discord.ui.View):
    """Select menu to choose the server for leave (DM with multiple guilds)."""

    def __init__(self, guilds: list[tuple[int, str]], role: str):
        """Build the server select menu for the given candidate guilds and role."""
        super().__init__(timeout=120)
        self.role = role
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
        """Handle server selection — perform leave."""
        guild_id = int(self.select.values[0])
        await _do_leave(interaction, guild_id, self.role, edit=True)


async def _get_registered_guilds(bot, user_id: int, db):
    """Return guilds where the user is registered as a player."""
    results: list[tuple[int, str]] = []
    for guild in bot.guilds:
        player = await Player.get(db, guild.id, user_id)
        if player and (player.can_submit or player.can_be_target):
            results.append((guild.id, guild.name))
    return results


async def _do_leave(
    interaction: discord.Interaction, guild_id: int, role: str, edit: bool = False
) -> None:
    """Perform the leave logic for a specific guild."""
    db = interaction.client.db  # type: ignore[attr-defined]

    existing = await Player.get(db, guild_id, interaction.user.id)
    if existing is None or (not existing.can_submit and not existing.can_be_target):
        msg = "❌ Tu n'es pas inscrit(e) sur ce serveur."
        if edit:
            await interaction.response.edit_message(content=msg, view=None)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    if role == PlayerRole.SUBMITTER:
        if not existing.can_submit:
            msg = "ℹ️ Tu n'es pas inscrit(e) comme rédacteur."
            if edit:
                await interaction.response.edit_message(content=msg, view=None)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return
        await Player.update(db, guild_id, interaction.user.id, can_submit=0)
        label = "rédacteur"
    elif role == PlayerRole.TARGET:
        if not existing.can_be_target:
            msg = "ℹ️ Tu n'es pas inscrit(e) comme cible."
            if edit:
                await interaction.response.edit_message(content=msg, view=None)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return
        await Player.update(db, guild_id, interaction.user.id, can_be_target=0)
        label = "cible"
    else:
        await Player.update(
            db, guild_id, interaction.user.id, can_submit=0, can_be_target=0
        )
        label = "tous les rôles"

    await cleanup_if_fully_removed(db, guild_id, interaction.user.id)

    msg = f"✅ Tu as quitté : {label}."
    if edit:
        await interaction.response.edit_message(content=msg, view=None)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


async def handle(interaction: discord.Interaction, role: str) -> None:
    """Self-service unregistration from a role or entirely."""
    if interaction.guild_id is not None:
        await _do_leave(interaction, interaction.guild_id, role)
        return

    db = interaction.client.db  # type: ignore[attr-defined]
    guilds = await _get_registered_guilds(interaction.client, interaction.user.id, db)

    if not guilds:
        await interaction.response.send_message(
            "❌ Tu n'es inscrit(e) sur aucun serveur.",
            ephemeral=True,
        )
        return

    if len(guilds) == 1:
        await _do_leave(interaction, guilds[0][0], role)
        return

    view = ServerSelectView(guilds, role)
    await interaction.response.send_message(
        "Choisis le serveur :",
        view=view,
        ephemeral=True,
    )
