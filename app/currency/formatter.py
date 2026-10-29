from datetime import datetime
from zoneinfo import ZoneInfo


class CurrencyFormatter:
    TEHRAN = ZoneInfo("Asia/Tehran")

    def format_prices(self, result: dict) -> str:
        lines = [
            "آخرین به‌روزرسانی:",
            self._format_time(result["last_updated"]),
            "منطقهٔ زمانی: تهران",
        ]
        if result.get("stale"):
            lines.append("توجه: دادهٔ منتشرشده ممکن است قدیمی باشد.")
        lines.append("------------------------------")
        for currency, quote in result["prices"].items():
            unit = "تومان"
            if currency.startswith("طلای"):
                unit += " برای هر گرم"
            lines.append(f"{currency}: {quote['value']:,.0f} {unit}")
        return "\n".join(lines)

    def _format_time(self, value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=self.TEHRAN)
            else:
                parsed = parsed.astimezone(self.TEHRAN)
            return parsed.strftime("%d %b %Y, %H:%M")
        except (AttributeError, TypeError, ValueError):
            return str(value)
