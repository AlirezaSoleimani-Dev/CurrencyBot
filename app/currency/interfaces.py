# app/currency/interfaces.py
from abc import ABC, abstractmethod

class CurrencyProvider(ABC):
    @abstractmethod
    async def get_latest_prices(self) -> dict:
        pass