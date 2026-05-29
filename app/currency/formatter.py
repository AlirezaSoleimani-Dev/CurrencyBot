class CurrencyFormatter:
    def format_prices(self, result: dict) -> str:
        lines = [(f" آخرین بروزرسانی:{result['last_updated']} ")]
        lines.append("-------------------------------------------")
        for currency, price in result['prices'].items():
            lines.append(f"{currency}: {price}")
        return "\n".join(lines)
