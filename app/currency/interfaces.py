# app/currency/interfaces.py
from abc import ABC, abstractmethod


class CurrencyProvider(ABC):
    @abstractmethod
    async def get_latest_prices(self) -> dict:
        pass

    @abstractmethod
    async def get_price_chart(self, price, interval):
        pass
