import logging

import httpx
from app.currency.interfaces import CurrencyProvider


logger = logging.getLogger(__name__)


class CurrencyApiClient(CurrencyProvider):
    def __init__(self, base_url: str, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    async def get_latest_prices(self) -> dict:
        params = {}
        if self.api_key:
            params["rev"] = self.api_key

        async with httpx.AsyncClient() as client:
            logger.info("Fetching latest currency prices")
            response = await client.get(self.base_url, params=params)
            response.raise_for_status()
            logger.info("Currency API responded with status_code=%s", response.status_code)
            return response.json()
