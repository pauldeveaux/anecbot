import discord

from anecbot.features.stats.service import build_player_stats_embed, get_player_stats


class PlayerStatsButton(discord.ui.Button):
    """One leaderboard row's button — opens that player's /stats player view."""

    def __init__(self, guild_id: int, user_id: int, name: str, row: int):
        """Build the button for this leaderboard row, labeled with the player's name."""
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label=name[:80],
            custom_id=f"leaderboard-player:{guild_id}:{user_id}",
            row=row,
        )
        self.user_id = user_id
        self.name = name

    async def callback(self, interaction: discord.Interaction):
        """Show this player's /stats player embed, ephemeral."""
        assert interaction.guild_id is not None
        db = interaction.client.db  # type: ignore[attr-defined]
        stats = await get_player_stats(db, interaction.guild_id, self.user_id)
        embed = build_player_stats_embed(stats, self.name)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class LeaderboardPlayerButtonsView(discord.ui.View):
    """One button per leaderboard row, opening that player's /stats player view."""

    def __init__(self, guild_id: int, entries: list[tuple[int, str]]):
        """Build one button per (user_id, name) entry, 5 per row like the embed's ranking."""
        super().__init__(timeout=None)
        for index, (user_id, name) in enumerate(entries):
            self.add_item(PlayerStatsButton(guild_id, user_id, name, row=index // 5))
