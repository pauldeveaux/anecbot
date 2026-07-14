import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info("Logged in as %s (guilds: %d)", bot.user, len(bot.guilds))

    return bot
