import os

from dotenv import load_dotenv

from anecbot.bot import create_bot
from anecbot.logging import setup_logging

load_dotenv()
setup_logging()

bot = create_bot()
bot.run(os.environ["DISCORD_TOKEN"])
