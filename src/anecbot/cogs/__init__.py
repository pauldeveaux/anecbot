from anecbot.cogs.admin import setup as setup_admin
from anecbot.cogs.general import setup as setup_general
from anecbot.cogs.player import setup as setup_player


async def setup(bot):
    """Load all cog subpackages."""
    await setup_admin(bot)
    await setup_general(bot)
    await setup_player(bot)
