import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv("TOKEN")
    BASE_URL = os.getenv("BASE_URL")
    CURRENCY_API_URL = os.getenv("CURRENCY_API_URL")
    CURRENCY_API_KEY = os.getenv("CURRENCY_API_KEY")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
