import discord

ITEMS_PER_PAGE = 20


class NavigablePagesView(discord.ui.View):
    """Base view for browsing pages with first/previous/next/last controls.

    Subclasses must implement `total_pages` and `build_embed()`.
    """

    def __init__(self, timeout: float = 120):
        """Start on the first page and sync the navigation buttons' disabled state."""
        super().__init__(timeout=timeout)
        self.page = 0
        self.sync_nav_buttons()

    @property
    def total_pages(self) -> int:
        """Return the total number of pages."""
        raise NotImplementedError

    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        raise NotImplementedError

    def sync_nav_buttons(self):
        """Enable/disable navigation buttons based on the current page."""
        at_first = self.page == 0
        at_last = self.page >= self.total_pages - 1
        self.first_button.disabled = at_first
        self.prev_button.disabled = at_first
        self.next_button.disabled = at_last
        self.last_button.disabled = at_last

    async def _go_to(self, interaction: discord.Interaction, page: int):
        """Move to the given page and refresh the message."""
        self.page = page
        self.sync_nav_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="⏮", style=discord.ButtonStyle.secondary, row=0)
    async def first_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Jump to the first page."""
        await self._go_to(interaction, 0)

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to the previous page."""
        await self._go_to(interaction, self.page - 1)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Go to the next page."""
        await self._go_to(interaction, self.page + 1)

    @discord.ui.button(label="⏭", style=discord.ButtonStyle.secondary, row=0)
    async def last_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        """Jump to the last page."""
        await self._go_to(interaction, self.total_pages - 1)


class PaginatedView(NavigablePagesView):
    """Paginated embed view showing a slice of text lines per page."""

    def __init__(
        self,
        items: list[str],
        title: str,
        color: discord.Color = discord.Color.blue(),
        per_page: int = ITEMS_PER_PAGE,
    ):
        """Store the items to paginate and the display settings for each page."""
        self.items = items
        self.title = title
        self.color = color
        self.per_page = per_page
        super().__init__(timeout=120)

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
