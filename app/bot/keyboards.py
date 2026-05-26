# app/bot/keyboards.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class BotKeyboards:
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "Get Latest currency price",
                    callback_data="get_latest_prices"
                )
            ]
        ])