import discord

from anecbot.cogs.admin.base import get_db
from anecbot.features.publisher.service import refresh_published_reveal_dates
from anecbot.models.enums import GuildTimezone
from anecbot.models.guild import Guild

MODE_LABELS: dict[GuildTimezone, str] = {
    GuildTimezone.EUROPE_PARIS: "France / Belgique (Europe/Paris)",
    GuildTimezone.EUROPE_BRUSSELS: "Belgique (Europe/Brussels)",
    GuildTimezone.EUROPE_ZURICH: "Suisse (Europe/Zurich)",
    GuildTimezone.EUROPE_LUXEMBOURG: "Luxembourg (Europe/Luxembourg)",
    GuildTimezone.EUROPE_LONDON: "Royaume-Uni (Europe/London)",
    GuildTimezone.AMERICA_TORONTO: "Québec / Canada Est (America/Toronto)",
    GuildTimezone.AMERICA_MARTINIQUE: "Martinique (America/Martinique)",
    GuildTimezone.AMERICA_GUADELOUPE: "Guadeloupe (America/Guadeloupe)",
    GuildTimezone.AMERICA_NEW_YORK: "États-Unis Est (America/New_York)",
    GuildTimezone.INDIAN_REUNION: "La Réunion (Indian/Reunion)",
    GuildTimezone.INDIAN_MAYOTTE: "Mayotte (Indian/Mayotte)",
    GuildTimezone.PACIFIC_NOUMEA: "Nouvelle-Calédonie (Pacific/Noumea)",
    GuildTimezone.PACIFIC_TAHITI: "Polynésie française (Pacific/Tahiti)",
    GuildTimezone.AFRICA_ABIDJAN: "Afrique de l'Ouest (Africa/Abidjan)",
    GuildTimezone.AFRICA_KINSHASA: "Afrique centrale (Africa/Kinshasa)",
    GuildTimezone.UTC: "UTC",
}


async def handle(interaction: discord.Interaction, tz: GuildTimezone):
    """Set the guild's timezone."""
    assert interaction.guild_id is not None
    db = get_db(interaction)
    await Guild.upsert(db, interaction.guild_id, timezone=tz)
    await refresh_published_reveal_dates(interaction.client, db, interaction.guild_id)
    await interaction.response.send_message(
        f"✅ Fuseau horaire configuré : {MODE_LABELS[tz]}",
        ephemeral=True,
    )
