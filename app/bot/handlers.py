import logging

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes

from app.currency.formatter import CurrencyFormatter

logger = logging.getLogger(__name__)


class CurrencyBotHandlers:
    def __init__(self, currency_service, currency_formatter: CurrencyFormatter):
        self.currency_service = currency_service
        self.currency_formatter = currency_formatter

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        logger.info("Start command received from user_id=%s", user.id if user else None)

        keyboard = [
            ["💵 Get Currency Prices"],
            # ["📈 Show Charts"]
        ]

        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )

        await update.message.reply_text(
            "Choose an option:",
            reply_markup=reply_markup
        )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text

        if text == "💵 Get Currency Prices":
            try:
                await update.message.reply_text("Fetching prices...")
                result = await self.currency_service.get_latest_prices()
                message = self.currency_formatter.format_prices(result)
                await update.message.reply_text(message)

            except Exception:
                logger.exception("Failed to send latest prices")
                await update.message.reply_text(
                    "Sorry, I could not get the latest prices right now."
                )
