from anecbot.cogs.admin import setup as setup_admin
from anecbot.cogs.general import setup as setup_general


async def setup(bot):
    """Load all cog subpackages."""
    await setup_admin(bot)
    await setup_general(bot)
