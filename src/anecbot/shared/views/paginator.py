import discord

ITEMS_PER_PAGE = 20


class PaginatedView(discord.ui.View):
    """Generic paginated embed view with navigation buttons."""

    def __init__(
        self,
        items: list[str],
        title: str,
        color: discord.Color = discord.Color.blue(),
        per_page: int = ITEMS_PER_PAGE,
    ):
        super().__init__(timeout=120)
        self.items = items
        self.title = title
        self.color = color
        self.per_page = per_page
        self.page = 0
        self._update_buttons()

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        return max(1, (len(self.items) + self.per_page - 1) // self.per_page)

    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        start = self.page * self.per_page
        end = start + self.per_page
        page_items = self.items[start:end]

        footer = f"Page {self.page + 1}/{self.total_pages} — {len(self.items)} au total"
        return discord.Embed(
            title=self.title,
            description="\n".join(page_items),
            color=self.color,
        ).set_footer(text=footer)

    def _update_buttons(self):
        """Enable/disable buttons based on current page."""
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page >= self.total_pages - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to previous page."""
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to next page."""
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
