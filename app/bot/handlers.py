import logging

from telegram import Update
from telegram.ext import ContextTypes
from app.bot.keyboards import BotKeyboards
from app.currency.formatter import CurrencyFormatter


logger = logging.getLogger(__name__)


class CurrencyBotHandlers:
    def __init__(self, currency_service, currency_formatter: CurrencyFormatter):
        self.currency_service = currency_service
        self.currency_formatter = currency_formatter

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        logger.info("Start command received from user_id=%s", user.id if user else None)

        await update.message.reply_text(
            "Welcome. Choose an option:",
            reply_markup=BotKeyboards.main_menu()
        )

    async def handle_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user = update.effective_user
        logger.info(
            "Callback received from user_id=%s data=%s",
            user.id if user else None,
            query.data,
        )

        if query.data == "get_latest_prices":
            await query.edit_message_text("Getting latest prices...")

            try:
                prices = await self.currency_service.get_latest_prices()
                message = self.currency_formatter.format_prices(prices)
                await query.edit_message_text(message)
                logger.info("Latest prices sent to user_id=%s", user.id if user else None)
            except Exception:
                logger.exception("Failed to send latest prices")
                await query.edit_message_text(
                    "Sorry, I could not get the latest prices right now."
                )
