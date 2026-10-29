import logging

import httpx

from app.currency.interfaces import CurrencyProvider

logger = logging.getLogger(__name__)


class IranMarketDataProvider(CurrencyProvider):
    """Fetch selected Iran free-market prices from the public Iran Market Data feed."""

    API_URL = (
        "https://raw.githubusercontent.com/iran-market/iran-market.github.io/"
        "main/data/popular.json"
    )
    HISTORY_URL = (
        "https://raw.githubusercontent.com/iran-market/iran-market.github.io/"
        "main/data/history/{symbol}.json"
    )
    SYMBOLS = {
        "USD_IRR_FREE": "دلار آمریکا (بازار آزاد)",
        "GOLD_18K_IRR": "طلای ۱۸ عیار (هر گرم)",
        "EUR_IRR_FREE": "یورو (بازار آزاد)",
        "GBP_IRR_FREE": "پوند انگلیس (بازار آزاد)",
    }

    async def get_latest_prices(self) -> dict:
        logger.info("Fetching latest Iran market prices")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.API_URL)
            response.raise_for_status()

        payload = response.json()
        records = payload.get("data")
        if not isinstance(records, list):
            raise ValueError("Iran Market Data response has no data list")

        by_symbol = {
            item.get("symbol"): item
            for item in records
            if isinstance(item, dict)
        }
        prices = {}
        timestamps = []
        stale = payload.get("meta", {}).get("stale", False)
        for symbol, label in self.SYMBOLS.items():
            item = by_symbol.get(symbol)
            if item is None or not isinstance(item.get("price"), (int, float)):
                raise ValueError(f"Iran Market Data response is missing {symbol}")
            prices[label] = {
                "value": item["price"],
                "unit": item.get("unit", "unit"),
            }
            if item.get("timestamp_tehran"):
                timestamps.append(item["timestamp_tehran"])
            stale = stale or item.get("stale", False)

        # These individual timestamps are Tehran local time and share a format.
        last_updated = (
            max(timestamps)
            if timestamps
            else payload.get("meta", {}).get("published_at", "Unknown")
        )
        return {
            "last_updated": last_updated,
            "unit": payload.get("meta", {}).get("unit", "toman"),
            "stale": stale,
            "prices": prices,
        }

    async def get_historical_prices(self, symbol: str) -> dict:
        if symbol not in self.SYMBOLS:
            raise ValueError(f"Unsupported history symbol: {symbol}")

        logger.info("Fetching historical prices for %s", symbol)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(self.HISTORY_URL.format(symbol=symbol))
            response.raise_for_status()
            payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid history response for {symbol}")
        return payload
