import logging
import time

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from app.config import Config
from app.bot.handlers import CurrencyBotHandlers
from app.currency.api_client import BitPinCurrencyProvider
from app.currency.service import CurrencyService
from app.currency.formatter import CurrencyFormatter
from app.core.logging_config import setup_logging
from telegram.ext import MessageHandler, filters

import datetime

logger = logging.getLogger(__name__)


def main():

    setup_logging(Config.LOG_LEVEL)
    logger.info("Starting currency bot")

    currency_provider = BitPinCurrencyProvider(base_url=Config.BITPIN_BASE_URL)

    currency_service = CurrencyService(currency_provider)
    currency_formatter = CurrencyFormatter()

    handlers = CurrencyBotHandlers(
        currency_service=currency_service, currency_formatter=currency_formatter
    )

    app = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(MessageHandler(filters.TEXT, handlers.handle_button))
    logger.info("Bot is running with long polling")
    app.run_polling()


if __name__ == "__main__":
    main()
