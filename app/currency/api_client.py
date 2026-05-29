import logging
import time
from datetime import datetime
import httpx

from app.currency.interfaces import CurrencyProvider

logger = logging.getLogger(__name__)


class BitPinCurrencyProvider(CurrencyProvider):
    def __init__(self, base_url: str):
        self.base_url = base_url

    async def get_latest_prices(self) -> dict:
        headers = {
            "Origin": "https://bitpin.ir",
            "Referer": "https://bitpin.ir/academy/live/currency/",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        }

        payload = {
            "action": (None, "bpa_price_landing_refresh"),
            "nonce": (None, "67baf604e8"),
            "landing_type": (None, "dollar"),
        }

        async with httpx.AsyncClient() as client:
            logger.info("Fetching latest currency prices")
            response = await client.post(self.base_url, files=payload, headers=headers,)
            response.raise_for_status()
            logger.info(
                "Currency API responded with status_code=%s", response.status_code
            )
            response_json = response.json()

            last_updated = datetime.fromtimestamp(
                response_json["data"]["last_updated"]
            ).strftime("%Y-%m-%d %H:%M:%S")

            clean_data = {
                "last_updated": last_updated,
                "prices": {
                    data['name']: f"{data['price']:,}"
                    for symbol, data in response_json["data"]["items"].items()
                }
            }
            return clean_data

    async def get_price_chart(self, price: str = "dollar", interval: str = "daily"):
        now = time.time()
