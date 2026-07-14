import logging
import os

from dotenv import load_dotenv

from anecbot.bot import create_bot

load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = create_bot()
bot.run(os.environ["DISCORD_TOKEN"])
