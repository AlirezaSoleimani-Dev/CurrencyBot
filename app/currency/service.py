# app/currency/service.py
import logging

from app.currency.interfaces import CurrencyProvider

logger = logging.getLogger(__name__)


class CurrencyService:
    def __init__(self, provider: CurrencyProvider):
        self.provider = provider

    async def get_latest_prices(self) -> dict:
        logger.debug("Requesting latest prices from provider")
        prices = await self.provider.get_latest_prices()
        logger.debug("Received %s price entries", len(prices) if prices else 0)
        return prices
