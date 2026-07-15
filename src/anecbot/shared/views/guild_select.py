from collections.abc import Awaitable, Callable

import discord


class GuildSelectView(discord.ui.View):
    """Select menu to choose among shared guilds, then delegate to a callback."""

    def __init__(
        self,
        guilds: list[tuple[int, str]],
        on_select: Callable[[discord.Interaction, int], Awaitable[None]],
    ):
        super().__init__(timeout=120)
        self._on_select = on_select
        options = [
            discord.SelectOption(label=name, value=str(gid)) for gid, name in guilds
        ]
        self.select = discord.ui.Select(
            placeholder="Choisis le serveur", options=options
        )
        self.select.callback = self._handle_select
        self.add_item(self.select)

    async def _handle_select(self, interaction: discord.Interaction):
        """Resolve the chosen guild id and delegate to the configured callback."""
        guild_id = int(self.select.values[0])
        await self._on_select(interaction, guild_id)
