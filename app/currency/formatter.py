# app/currency/formatter.py
class CurrencyFormatter:
    def format_prices(self, prices: dict) -> str:
        lines = ["Latest currency prices:\n"]

        for currency, price in prices.items():
            lines.append(f"{currency}: {price}")

        return "\n".join(lines)