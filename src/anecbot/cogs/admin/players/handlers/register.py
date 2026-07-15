import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.players.handlers.registration import send_dm
from anecbot.models.enums import PlayerRole
from anecbot.models.guild import Guild
from anecbot.models.player import Player

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

    await interaction.response.send_message(
        f"✅ {user.mention} inscrit(e) comme {label}.",
        ephemeral=True,
    )

    guild_name = interaction.guild.name if interaction.guild else "le serveur"
    dm_label = (
        "envoyer des anecdotes" if role == PlayerRole.SUBMITTER else "être la cible"
    )
    if role == PlayerRole.ALL:
        dm_label = "envoyer et être la cible"
    await send_dm(user, guild_name, dm_label)
