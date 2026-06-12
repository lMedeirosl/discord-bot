# config.py
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

BOT_PREFIX = os.getenv("BOT_PREFIX", "!")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/database.sqlite")
DAILY_REWARD = int(os.getenv("DAILY_REWARD", "100"))
DAILY_COOLDOWN_HOURS = int(os.getenv("DAILY_COOLDOWN_HOURS", "24"))
ITEMS_JSON_DIR = os.getenv("ITEMS_JSON_DIR", "assets/items")
