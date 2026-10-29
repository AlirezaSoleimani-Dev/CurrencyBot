from datetime import date, datetime, timedelta
from io import BytesIO
import threading
from zoneinfo import ZoneInfo

import matplotlib

matplotlib.use("Agg")

from matplotlib import dates as mdates
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter

_PLOT_LOCK = threading.Lock()


def render_price_chart(records: list[dict], title: str, days: int) -> BytesIO:
    cutoff = (
        datetime.now(ZoneInfo("Asia/Tehran")).date() - timedelta(days=days - 1)
    )
    month = [
        (datetime.strptime(row["date"], "%Y-%m-%d"), row["close"])
        for row in records
        if date.fromisoformat(row["date"]) >= cutoff
    ]
    if not month:
        raise ValueError(f"No history is available for the last {days} days")

    month.sort(key=lambda item: item[0])
    dates, prices = zip(*month)

    with _PLOT_LOCK:
        figure = Figure(figsize=(9, 5), layout="constrained")
        canvas = FigureCanvasAgg(figure)
        axis = figure.subplots()
        axis.plot(
            dates,
            prices,
            color="#1769aa",
            marker="o",
            markersize=3,
            linewidth=2,
        )
        axis.fill_between(dates, prices, min(prices), color="#1769aa", alpha=0.10)
        axis.set_title(f"{title} — last {days} days")
        axis.set_xlabel("Date")
        axis.set_ylabel("Price (toman)")
        axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.0f}"))
        axis.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=8))
        axis.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        axis.grid(True, alpha=0.25)
        figure.autofmt_xdate()

        image = BytesIO()
        canvas.print_png(image)
        image.seek(0)
        figure.clear()
        return image
