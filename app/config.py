import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TOKEN")
    TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
    TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
    MT_PROXY_URL = os.getenv("MT_PROXY_URL")
    MT_PROXY_HOST = os.getenv("MT_PROXY_HOST")
    MT_PROXY_PORT = os.getenv("MT_PROXY_PORT")
    MT_PROXY_SECRET = os.getenv("MT_PROXY_SECRET")
    TELEGRAM_SESSION = os.getenv("TELEGRAM_SESSION", "currency_bot")
    HISTORY_CACHE_DB = os.getenv("HISTORY_CACHE_DB", "data/history.sqlite3")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
