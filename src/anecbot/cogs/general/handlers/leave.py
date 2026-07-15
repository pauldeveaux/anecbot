import discord

from anecbot.models.enums import PlayerRole
from anecbot.models.player import Player


async def handle(interaction: discord.Interaction, role: str) -> None:
    """Self-service unregistration from a role or entirely."""
    assert interaction.guild_id is not None
    db = interaction.client.db  # type: ignore[attr-defined]

    existing = await Player.get(db, interaction.guild_id, interaction.user.id)
    if existing is None:
        await interaction.response.send_message(
            "❌ Tu n'es pas inscrit(e).",
            ephemeral=True,
        )
        return

    if role == PlayerRole.SUBMITTER:
        if not existing.can_submit:
            await interaction.response.send_message(
                "ℹ️ Tu n'es pas inscrit(e) comme rédacteur.",
                ephemeral=True,
            )
            return
        await Player.update(db, interaction.guild_id, interaction.user.id, can_submit=0)
        label = "rédacteur"
    elif role == PlayerRole.TARGET:
        if not existing.can_be_target:
            await interaction.response.send_message(
                "ℹ️ Tu n'es pas inscrit(e) comme cible.",
                ephemeral=True,
            )
            return
        await Player.update(
            db, interaction.guild_id, interaction.user.id, can_be_target=0
        )
        label = "cible"
    else:
        label = "tous les rôles"

    updated = await Player.get(db, interaction.guild_id, interaction.user.id)
    if (
        updated
        and not updated.can_submit
        and not updated.can_be_target
        and not updated.banned_submit
        and not updated.banned_target
    ):
        await Player.delete(db, interaction.guild_id, interaction.user.id)

    await interaction.response.send_message(
        f"✅ Tu as quitté : {label}.",
        ephemeral=True,
    )
