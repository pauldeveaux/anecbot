from anecbot.cogs.admin import ConfigCog
from anecbot.cogs.admin import setup as setup_admin

__all__ = ["ConfigCog"]


async def setup(bot):
    """Load all cog subpackages."""
    await setup_admin(bot)
