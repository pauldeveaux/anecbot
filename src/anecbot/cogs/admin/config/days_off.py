import discord

from anecbot.cogs.admin.base import get_db
from anecbot.models.guild import Guild
from anecbot.utils.time import parse_days_off


async def handle(interaction: discord.Interaction, jours: str):
    """Set the days off (weekdays with no publication)."""
    try:
        days = parse_days_off(jours)
    except ValueError:
        await interaction.response.send_message(
            "❌ Format invalide. Utilise des numéros de jour (0=lundi, 6=dimanche) "
            "séparés par des virgules (ex: 5,6).",
            ephemeral=True,
        )
        return

    if any(day < 0 or day > 6 for day in days):
        await interaction.response.send_message(
            "❌ Les jours doivent être compris entre 0 (lundi) et 6 (dimanche).",
            ephemeral=True,
        )
        return

    if len(days) >= 7:
        await interaction.response.send_message(
            "❌ Impossible de désactiver tous les jours : il doit rester au moins "
            "un jour actif.",
            ephemeral=True,
        )
        return

    normalized = ",".join(str(day) for day in sorted(days))
    await Guild.upsert(get_db(interaction), interaction.guild_id, days_off=normalized)
    label = normalized if normalized else "aucun"
    await interaction.response.send_message(
        f"✅ Jours sans publication configurés : {label}",
        ephemeral=True,
    )
