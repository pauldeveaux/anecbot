import discord

from anecbot.cogs.admin.base import get_db
from anecbot.cogs.admin.config.leaderboard_reset_format import (
    DEFAULT_ANCHORS,
    format_leaderboard_reset_anchor,
)
from anecbot.models.enums import LeaderboardResetMode
from anecbot.models.guild import Guild

MODE_LABELS: dict[LeaderboardResetMode, str] = {
    LeaderboardResetMode.NEVER: "jamais",
    LeaderboardResetMode.DAILY: "quotidien",
    LeaderboardResetMode.WEEKLY: "hebdomadaire",
    LeaderboardResetMode.MONTHLY: "mensuel",
    LeaderboardResetMode.YEARLY: "annuel",
}


async def handle(interaction: discord.Interaction, mode: LeaderboardResetMode):
    """Set the leaderboard reset cadence unit, resetting the anchor to its default."""
    anchor = DEFAULT_ANCHORS[mode]
    kwargs: dict[str, object] = {
        "leaderboard_reset_mode": mode,
        "leaderboard_reset_anchor": anchor,
    }
    if mode == LeaderboardResetMode.NEVER:
        kwargs["leaderboard_reset_interval"] = 1
    await Guild.upsert(get_db(interaction), interaction.guild_id, **kwargs)
    message = f"✅ Fréquence de reset du leaderboard configurée : {MODE_LABELS[mode]}."
    if mode not in (LeaderboardResetMode.NEVER, LeaderboardResetMode.DAILY):
        anchor_label = format_leaderboard_reset_anchor(mode, anchor)
        message += (
            f" Jour de reset par défaut : {anchor_label} "
            "(modifiable avec `/config leaderboard-reset-day`)."
        )
    await interaction.response.send_message(message, ephemeral=True)
