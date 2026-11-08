import logging

import httpx

from app.currency.interfaces import CurrencyProvider

logger = logging.getLogger(__name__)


class NerkhAraProvider(CurrencyProvider):
    """Fetch Iranian free-market prices and daily history from NerkhAra's API."""

    API_URL = "https://nerkhara.com/api/v1"
    ATTRIBUTION = "NerkhAra (https://nerkhara.com)"
    SYMBOLS = {
        "USD_IRR_FREE": "دلار آمریکا (بازار آزاد)",
        "GOLD_18K_IRR": "طلای ۱۸ عیار (هر گرم)",
        "EUR_IRR_FREE": "یورو (بازار آزاد)",
        "GBP_IRR_FREE": "پوند انگلیس (بازار آزاد)",
    }
    API_SYMBOLS = {
        "USD_IRR_FREE": "usd",
        "GOLD_18K_IRR": "gold-18k",
        "EUR_IRR_FREE": "eur",
        "GBP_IRR_FREE": "gbp",
    }

    async def get_latest_prices(self) -> dict:
        logger.info("Fetching latest prices from NerkhAra")
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{self.API_URL}/latest.json")
            response.raise_for_status()

        payload = response.json()
        records = payload.get("items")
        if not isinstance(records, list):
            raise ValueError("NerkhAra response has no items list")

        by_id = {
            item.get("id"): item for item in records if isinstance(item, dict)
        }
        prices = {}
        timestamps = []
        stale = bool(payload.get("stale", False))
        for symbol, label in self.SYMBOLS.items():
            item = by_id.get(self.API_SYMBOLS[symbol])
            if item is None or not isinstance(item.get("price"), (int, float)):
                raise ValueError(
                    f"NerkhAra response is missing {self.API_SYMBOLS[symbol]}"
                )
            if item.get("unit") != "IRT":
                raise ValueError(
                    f"Unexpected NerkhAra unit for {self.API_SYMBOLS[symbol]}: "
                    f"{item.get('unit')}"
                )
            prices[label] = {"value": item["price"], "unit": "toman"}
            timestamp = item.get("updated_utc")
            if timestamp:
                timestamps.append(self._as_utc(timestamp))
            stale = stale or bool(item.get("stale", False))

        last_updated = max(timestamps) if timestamps else self._as_utc(
            payload.get("generated_utc", "Unknown")
        )
        return {
            "last_updated": last_updated,
            "unit": "toman",
            "stale": stale,
            "source": self.ATTRIBUTION,
            "prices": prices,
        }

    async def get_historical_prices(self, symbol: str) -> dict:
        if symbol not in self.SYMBOLS:
            raise ValueError(f"Unsupported history symbol: {symbol}")

        api_symbol = self.API_SYMBOLS[symbol]
        logger.info("Fetching NerkhAra historical prices for %s", api_symbol)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.API_URL}/history/{api_symbol}.json"
            )
            response.raise_for_status()
            payload = response.json()

        points = payload.get("points") if isinstance(payload, dict) else None
        if not isinstance(points, list):
            raise ValueError(f"NerkhAra history response has no points for {symbol}")

        # Keep the history cache's existing input format. NerkhAra publishes
        # daily [YYYY-MM-DD, price] pairs; charting and forecasts use close values.
        return {
            "data": [
                {"t": point[0], "close": point[1]}
                for point in points
                if isinstance(point, list)
                and len(point) >= 2
                and isinstance(point[0], str)
                and isinstance(point[1], (int, float))
            ]
        }

    @staticmethod
    def _as_utc(value) -> str:
        if not isinstance(value, str) or value == "Unknown":
            return str(value)
        # NerkhAra documents updated_utc as UTC, though its timestamps omit Z.
        return value if value.endswith(("Z", "+00:00")) else f"{value}Z"
