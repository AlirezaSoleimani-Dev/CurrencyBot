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
    ALERTS_BUTTON = "🔔 Price alerts"
    CREATE_ALERT_BUTTON = "➕ Create alert"
    LIST_ALERTS_BUTTON = "📋 My alerts"
    ALERTS_BACK_BUTTON = "↩️ Back to alerts"
    CANCEL_ALERT_SETUP_BUTTON = "❌ Cancel setup"
    CANCEL_ALERT_PREFIX = "❌ Cancel alert #"
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
    ALERT_ASSETS = {
        "🔔 US Dollar": (
            "USD_IRR_FREE",
            "US Dollar (open market)",
            "دلار آمریکا (بازار آزاد)",
        ),
        "🔔 Euro": (
            "EUR_IRR_FREE",
            "Euro (open market)",
            "یورو (بازار آزاد)",
        ),
        "🔔 British Pound": (
            "GBP_IRR_FREE",
            "British Pound (open market)",
            "پوند انگلیس (بازار آزاد)",
        ),
        "🔔 18K Gold": (
            "GOLD_18K_IRR",
            "18K Gold (per gram)",
            "طلای ۱۸ عیار (هر گرم)",
        ),
    }

    def __init__(
        self,
        currency_service,
        currency_formatter: CurrencyFormatter,
        history_cache,
        alert_store,
    ):
        self.currency_service = currency_service
        self.currency_formatter = currency_formatter
        self.history_cache = history_cache
        self.alert_store = alert_store
        self._selected_chart_days = {}
        self._pending_alerts = {}

    @staticmethod
    def main_menu_buttons():
        return [
            [Button.text("💵 Get Currency Prices", resize=True)],
            [Button.text(CurrencyBotHandlers.CHART_BUTTON, resize=True)],
            [Button.text(CurrencyBotHandlers.FORECAST_BUTTON, resize=True)],
            [Button.text(CurrencyBotHandlers.ALERTS_BUTTON, resize=True)],
        ]

    async def handle_message(self, event):
        text = event.raw_text.strip()
        command = text.split(maxsplit=1)[0].split("@")[0] if text else ""
        user_key = (event.chat_id, event.sender_id)

        if command == "/start":
            self._pending_alerts.pop(user_key, None)
            logger.info("Start command received")
            await event.respond("Choose an option:", buttons=self.main_menu_buttons())
        elif text == self.BACK_BUTTON:
            self._pending_alerts.pop(user_key, None)
            self._selected_chart_days.pop((event.chat_id, event.sender_id), None)
            await event.respond("Choose an option:", buttons=self.main_menu_buttons())
        elif text == self.ALERTS_BUTTON:
            self._pending_alerts.pop(user_key, None)
            await self._show_alert_menu(event)
        elif text == self.CREATE_ALERT_BUTTON:
            self._pending_alerts.pop(user_key, None)
            await self._show_alert_assets(event)
        elif text in self.ALERT_ASSETS:
            await self._begin_alert_setup(event, user_key, text)
        elif text == self.LIST_ALERTS_BUTTON:
            self._pending_alerts.pop(user_key, None)
            await self._show_user_alerts(event)
        elif text == self.ALERTS_BACK_BUTTON:
            self._pending_alerts.pop(user_key, None)
            await self._show_alert_menu(event)
        elif text == self.CANCEL_ALERT_SETUP_BUTTON:
            self._pending_alerts.pop(user_key, None)
            await self._show_alert_menu(event, "Alert setup cancelled.")
        elif text.startswith(self.CANCEL_ALERT_PREFIX):
            self._pending_alerts.pop(user_key, None)
            await self._cancel_alert(event, text)
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
        elif user_key in self._pending_alerts:
            await self._save_alert_from_message(event, user_key, text)

    async def _show_chart_periods(self, event):
        buttons = [
            [Button.text("📅 1 month"), Button.text("📅 3 months")],
            [Button.text("📅 6 months")],
            [Button.text(self.BACK_BUTTON)],
        ]
        await event.respond("Choose a chart period:", buttons=buttons)

    async def _show_alert_menu(self, event, notice: str | None = None):
        buttons = [
            [Button.text(self.CREATE_ALERT_BUTTON)],
            [Button.text(self.LIST_ALERTS_BUTTON)],
            [Button.text(self.BACK_BUTTON)],
        ]
        message = "Price alerts: get one message when a price crosses your target."
        if notice:
            message = f"{notice}\n\n{message}"
        await event.respond(message, buttons=buttons)

    async def _show_alert_assets(self, event):
        buttons = [
            [Button.text("🔔 US Dollar"), Button.text("🔔 Euro")],
            [Button.text("🔔 British Pound"), Button.text("🔔 18K Gold")],
            [Button.text(self.ALERTS_BACK_BUTTON)],
        ]
        await event.respond("Choose an asset for your alert:", buttons=buttons)

    async def _begin_alert_setup(self, event, user_key, button_text: str):
        symbol, title, price_label = self.ALERT_ASSETS[button_text]
        try:
            result = await self.currency_service.get_latest_prices()
            quote = result.get("prices", {}).get(price_label)
            if result.get("stale") or not quote:
                raise ValueError("Latest price data is stale or unavailable")
            current_price = float(quote["value"])
            self._pending_alerts[user_key] = {
                "symbol": symbol,
                "title": title,
                "price_label": price_label,
                "current_price": current_price,
            }
            await event.respond(
                f"{title}\nCurrent price: {current_price:,.0f} toman\n\n"
                "Send your target price in toman as a whole number. "
                "The alert will trigger once the price crosses it.",
                buttons=[[Button.text(self.CANCEL_ALERT_SETUP_BUTTON)]],
            )
        except Exception:
            self._pending_alerts.pop(user_key, None)
            logger.exception("Could not start an alert for %s", symbol)
            await event.respond("Sorry, I could not fetch the current price to set up an alert.")

    @staticmethod
    def _parse_target_price(text: str) -> int | None:
        digits = str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
            "01234567890123456789",
        )
        normalized = text.translate(digits).replace(",", "").replace("٬", "").replace(" ", "")
        if not normalized.isdigit() or len(normalized) > 15:
            return None
        try:
            value = int(normalized)
        except ValueError:
            return None
        return value if value > 0 else None

    async def _save_alert_from_message(self, event, user_key, text: str):
        setup = self._pending_alerts[user_key]
        target = self._parse_target_price(text)
        if target is None:
            await event.respond(
                "Please send a positive whole-number target in toman, for example 950000."
            )
            return
        current = setup["current_price"]
        if target == current:
            await event.respond(
                "Choose a target above or below the current price "
                f"({current:,.0f} toman)."
            )
            return

        direction = "above" if target > current else "below"
        try:
            alert_id = self.alert_store.create(
                chat_id=event.chat_id,
                user_id=event.sender_id,
                symbol=setup["symbol"],
                title=setup["title"],
                price_label=setup["price_label"],
                target=target,
                direction=direction,
            )
        except ValueError as exc:
            self._pending_alerts.pop(user_key, None)
            await event.respond(str(exc), buttons=self.main_menu_buttons())
            return
        except Exception:
            logger.exception("Failed to save a price alert")
            await event.respond("Sorry, I could not save that alert right now.")
            return

        self._pending_alerts.pop(user_key, None)
        relation = "above" if direction == "above" else "below"
        await event.respond(
            f"Alert #{alert_id} set: {setup['title']} when it goes {relation} "
            f"{target:,.0f} toman. I’ll notify you once it crosses the target.",
            buttons=self.main_menu_buttons(),
        )

    async def _show_user_alerts(self, event):
        alerts = self.alert_store.get_for_user(event.chat_id, event.sender_id)
        if not alerts:
            await event.respond(
                "You have no active price alerts.",
                buttons=[
                    [Button.text(self.CREATE_ALERT_BUTTON)],
                    [Button.text(self.ALERTS_BACK_BUTTON)],
                ],
            )
            return
        lines = ["Your active price alerts:"]
        buttons = []
        for alert in alerts:
            relation = "above" if alert["direction"] == "above" else "below"
            lines.append(
                f"#{alert['id']} {alert['title']}: {relation} "
                f"{alert['target']:,.0f} toman"
            )
            buttons.append([Button.text(f"{self.CANCEL_ALERT_PREFIX}{alert['id']}")])
        buttons.append([Button.text(self.ALERTS_BACK_BUTTON)])
        await event.respond("\n".join(lines), buttons=buttons)

    async def _cancel_alert(self, event, text: str):
        try:
            alert_id = int(text.removeprefix(self.CANCEL_ALERT_PREFIX))
        except ValueError:
            await event.respond("That alert number is invalid.")
            return
        if self.alert_store.cancel(alert_id, event.chat_id, event.sender_id):
            await event.respond(f"Alert #{alert_id} cancelled.")
        else:
            await event.respond("That alert is no longer active.")
        await self._show_user_alerts(event)
