import logging

from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from app.config import Config
from app.bot.handlers import CurrencyBotHandlers
from app.currency.api_client import CurrencyApiClient
from app.currency.service import CurrencyService
from app.currency.formatter import CurrencyFormatter
from app.core.logging_config import setup_logging


logger = logging.getLogger(__name__)


def main():
    setup_logging(Config.LOG_LEVEL)
    logger.info("Starting currency bot")

    currency_client = CurrencyApiClient(
        base_url=Config.CURRENCY_API_URL, api_key=Config.CURRENCY_API_KEY
    )

    currency_service = CurrencyService(currency_client)
    currency_formatter = CurrencyFormatter()

    handlers = CurrencyBotHandlers(
        currency_service=currency_service, currency_formatter=currency_formatter
    )

    app = (
        ApplicationBuilder()
        .token(Config.TELEGRAM_BOT_TOKEN)
        .base_url(Config.BASE_URL)
        .build()
    )

    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CallbackQueryHandler(handlers.handle_button))

    logger.info("Bot is running with long polling")
    app.run_polling()


if __name__ == "__main__":
    main()
