import logging

import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.players.handlers.registration import send_dm
from anecbot.features.player.service import MAX_TARGETS, can_register_as_target
from anecbot.models.enums import PlayerRole
from anecbot.models.guild import Guild
from anecbot.models.player import Player

logger = logging.getLogger(__name__)

ROLE_LABELS = {
    PlayerRole.SUBMITTER: "rédacteur",
    PlayerRole.TARGET: "cible",
}


async def handle(
    interaction: discord.Interaction, user: discord.Member, role: str
) -> None:
    """Admin-register a user with the given role."""
    assert interaction.guild_id is not None
    db = get_db(interaction)

    existing = await Player.get(db, interaction.guild_id, user.id)

    if (
        role in (PlayerRole.SUBMITTER, PlayerRole.ALL)
        and existing
        and existing.banned_submit
    ):
        await interaction.response.send_message(
            f"❌ {user.mention} est banni(e) en tant que rédacteur.",
            ephemeral=True,
        )
        return
    if (
        role in (PlayerRole.TARGET, PlayerRole.ALL)
        and existing
        and existing.banned_target
    ):
        await interaction.response.send_message(
            f"❌ {user.mention} est banni(e) en tant que cible.",
            ephemeral=True,
        )
        return
    if role in (
        PlayerRole.TARGET,
        PlayerRole.ALL,
    ) and not await can_register_as_target(db, interaction.guild_id, user.id):
        await interaction.response.send_message(
            f"❌ Le nombre maximum de cibles ({MAX_TARGETS}) est atteint pour ce serveur.",
            ephemeral=True,
        )
        return

    kwargs: dict[str, object] = {}
    if role in (PlayerRole.SUBMITTER, PlayerRole.ALL):
        kwargs["can_submit"] = 1
    if role in (PlayerRole.TARGET, PlayerRole.ALL):
        kwargs["can_be_target"] = 1

    await Guild.upsert(db, interaction.guild_id)
    await Player.upsert(db, interaction.guild_id, user.id, **kwargs)

    if role == PlayerRole.ALL:
        label = "rédacteur et cible"
    else:
        label = ROLE_LABELS[PlayerRole(role)]

    logger.info(
        "User %s registered as %s in guild %s", user.id, label, interaction.guild_id
    )
    await interaction.response.send_message(
        f"✅ {user.mention} inscrit(e) comme {label}.",
        ephemeral=True,
    )

    if role == PlayerRole.TARGET:
        return

    guild_name = interaction.guild.name if interaction.guild else "le serveur"
    await send_dm(user, guild_name, "envoyer des anecdotes")
