import discord

from anecbot.cogs.admin.config import ConfigCog

__all__ = ["ConfigCog"]

_ADMIN_PERMS = discord.Permissions(administrator=True)


async def setup(bot):
    """Load all admin cogs and set default_permissions on their commands."""
    cogs = [ConfigCog(bot)]
    for cog in cogs:
        for cmd in cog.walk_app_commands():
            cmd.default_permissions = _ADMIN_PERMS
        await bot.add_cog(cog)
