import asyncio
import logging

from telethon import Button

from app.currency.chart import render_price_chart
from app.currency.forecast import forecast_next_week
from app.currency.formatter import CurrencyFormatter

logger = logging.getLogger(__name__)


class CurrencyBotHandlers:
    CHART_BUTTON = "📈 Price charts"
    FORECAST_BUTTON = "🔮 7-day forecast"
    BACK_BUTTON = "↩️ Back to main menu"
    BACK_TO_PERIODS_BUTTON = "↩️ Back to periods"
    CHART_PERIODS = {
        "📅 1 month": 30,
        "📅 3 months": 90,
        "📅 6 months": 180,
    }
    CHART_ASSETS = {
        "🇺🇸 US Dollar": ("USD_IRR_FREE", "US Dollar (open market)"),
        "🇪🇺 Euro": ("EUR_IRR_FREE", "Euro (open market)"),
        "🇬🇧 British Pound": ("GBP_IRR_FREE", "British Pound (open market)"),
        "🥇 18K Gold": ("GOLD_18K_IRR", "18K Gold (per gram)"),
    }
    FORECAST_ASSETS = {
        "🔮 US Dollar": ("USD_IRR_FREE", "US Dollar (open market)"),
        "🔮 Euro": ("EUR_IRR_FREE", "Euro (open market)"),
        "🔮 British Pound": ("GBP_IRR_FREE", "British Pound (open market)"),
        "🔮 18K Gold": ("GOLD_18K_IRR", "18K Gold (per gram)"),
    }

    def __init__(
        self,
        currency_service,
        currency_formatter: CurrencyFormatter,
        history_cache,
    ):
        self.currency_service = currency_service
        self.currency_formatter = currency_formatter
        self.history_cache = history_cache
        self._selected_chart_days = {}

    @staticmethod
    def main_menu_buttons():
        return [
            [Button.text("💵 Get Currency Prices", resize=True)],
            [Button.text(CurrencyBotHandlers.CHART_BUTTON, resize=True)],
            [Button.text(CurrencyBotHandlers.FORECAST_BUTTON, resize=True)],
        ]

    async def handle_message(self, event):
        text = event.raw_text.strip()
        command = text.split(maxsplit=1)[0].split("@")[0] if text else ""

        if command == "/start":
            logger.info("Start command received")
            await event.respond("Choose an option:", buttons=self.main_menu_buttons())
        elif text == self.BACK_BUTTON:
            self._selected_chart_days.pop((event.chat_id, event.sender_id), None)
            await event.respond("Choose an option:", buttons=self.main_menu_buttons())
        elif text == "💵 Get Currency Prices":
            try:
                await event.respond("Fetching prices...")
                result = await self.currency_service.get_latest_prices()
                await event.respond(self.currency_formatter.format_prices(result))
            except Exception:
                logger.exception("Failed to send latest prices")
                await event.respond(
                    "Sorry, I could not get the latest prices right now."
                )
        elif text == self.CHART_BUTTON:
            await self._show_chart_periods(event)
        elif text == self.FORECAST_BUTTON:
            buttons = [
                [Button.text("🔮 US Dollar"), Button.text("🔮 Euro")],
                [Button.text("🔮 British Pound"), Button.text("🔮 18K Gold")],
                [Button.text(self.BACK_BUTTON)],
            ]
            await event.respond(
                "Choose an asset for a seven-day estimate:", buttons=buttons
            )
        elif text in self.FORECAST_ASSETS:
            symbol, title = self.FORECAST_ASSETS[text]
            try:
                await event.respond("Calculating the seven-day estimate...")
                history = await self.history_cache.get_history(symbol)
                forecast = forecast_next_week(history["records"])
                message = (
                    f"{title} — 7-day estimate\n"
                    f"Latest price: {forecast['latest_price']:,.0f} toman"
                )
                if forecast["last_date"]:
                    message += f" ({forecast['last_date']})"
                message += (
                    f"\nEstimate: {forecast['forecast_price']:,.0f} toman"
                    f"\nRecent backtest range: "
                    f"{forecast['range_low']:,.0f}–{forecast['range_high']:,.0f} toman"
                    f"\nModel: {forecast['model']}"
                    f"\nMedian backtest error: "
                    f"{forecast['backtest_error_pct']:.1f}% over "
                    f"{forecast['backtest_count']} rolling forecasts"
                    "\nThis is an estimate, not a guaranteed future price."
                )
                if history["stale"]:
                    message += "\nUsing cached historical data; refresh failed."
                await event.respond(message)
            except Exception:
                logger.exception("Failed to forecast %s", symbol)
                await event.respond(
                    "Sorry, I could not create that estimate right now."
                )
        elif text == self.BACK_TO_PERIODS_BUTTON:
            await self._show_chart_periods(event)
        elif text in self.CHART_PERIODS:
            self._selected_chart_days[(event.chat_id, event.sender_id)] = (
                self.CHART_PERIODS[text]
            )
            buttons = [
                [Button.text("🇺🇸 US Dollar"), Button.text("🇪🇺 Euro")],
                [Button.text("🇬🇧 British Pound"), Button.text("🥇 18K Gold")],
                [Button.text(self.BACK_TO_PERIODS_BUTTON)],
            ]
            await event.respond(
                f"Choose an asset for the last {self.CHART_PERIODS[text]} days:",
                buttons=buttons,
            )
        elif text in self.CHART_ASSETS:
            symbol, title = self.CHART_ASSETS[text]
            days = self._selected_chart_days.get(
                (event.chat_id, event.sender_id), 30
            )
            try:
                await event.respond(f"Loading the last {days} days of prices...")
                history = await self.history_cache.get_history(symbol)
                chart = await asyncio.to_thread(
                    render_price_chart, history["records"], title, days
                )
                chart.name = f"price-chart-{days}-days.png"
                caption = (
                    f"{title}\n{days}-day price history in toman\n"
                    f"Cache refreshed: {history['refreshed_at']} Tehran time"
                )
                if history["stale"]:
                    caption += "\nShowing cached data; refresh failed."
                await event.client.send_file(
                    event.chat_id,
                    chart,
                    caption=caption,
                    force_document=False,
                )
            except Exception:
                logger.exception("Failed to create the monthly chart for %s", symbol)
                await event.respond(
                    "Sorry, I could not create that chart right now."
                )

    async def _show_chart_periods(self, event):
        buttons = [
            [Button.text("📅 1 month"), Button.text("📅 3 months")],
            [Button.text("📅 6 months")],
            [Button.text(self.BACK_BUTTON)],
        ]
        await event.respond("Choose a chart period:", buttons=buttons)
