import asyncio
import json
import logging
import sqlite3
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from app.currency.api_client import IranMarketDataProvider

logger = logging.getLogger(__name__)


class SQLiteHistoryCache:
    """Persist a rolling window of daily prices, refreshing it every 12 hours."""

    REFRESH_SECONDS = 12 * 60 * 60
    RETAIN_DAYS = 180
    TEHRAN = ZoneInfo("Asia/Tehran")

    def __init__(self, database_path: str, provider: IranMarketDataProvider):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.provider = provider
        self._locks = {symbol: asyncio.Lock() for symbol in provider.SYMBOLS}
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path, timeout=10)

    def _initialize(self):
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS daily_prices (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    date_jalali TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL NOT NULL,
                    quality TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (symbol, date)
                )"""
            )
            db.execute(
                """CREATE TABLE IF NOT EXISTS cache_state (
                    symbol TEXT PRIMARY KEY,
                    fetched_at REAL NOT NULL
                )"""
            )

    def _read(self, symbol: str):
        with self._connect() as db:
            state = db.execute(
                "SELECT fetched_at FROM cache_state WHERE symbol = ?", (symbol,)
            ).fetchone()
            rows = db.execute(
                """SELECT date, date_jalali, open, high, low, close, quality
                   FROM daily_prices WHERE symbol = ? ORDER BY date""",
                (symbol,),
            ).fetchall()

        records = [
            {
                "date": row[0],
                "date_jalali": row[1],
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "quality": json.loads(row[6]),
            }
            for row in rows
        ]
        return (state[0] if state else None), records

    async def get_history(self, symbol: str) -> dict:
        if symbol not in self._locks:
            raise ValueError(f"Unsupported history symbol: {symbol}")

        async with self._locks[symbol]:
            fetched_at, records = self._read(symbol)
            now = datetime.now(timezone.utc).timestamp()
            if records and fetched_at and now - fetched_at < self.REFRESH_SECONDS:
                return self._result(records, fetched_at, stale=False)

            try:
                payload = await self.provider.get_historical_prices(symbol)
                records = self._normalize(payload)
                if not records:
                    raise ValueError(f"No historical prices returned for {symbol}")
                self._store(symbol, records, now)
                logger.info(
                    "Updated SQLite history cache for %s (%s rows)",
                    symbol,
                    len(records),
                )
                return self._result(records, now, stale=False)
            except Exception:
                if records and fetched_at:
                    logger.exception(
                        "History refresh failed for %s; serving cached data", symbol
                    )
                    return self._result(records, fetched_at, stale=True)
                raise

    def _normalize(self, payload: dict) -> list[dict]:
        entries = payload.get("data")
        if not isinstance(entries, list):
            raise ValueError("Historical price response has no data list")

        cutoff = datetime.now(self.TEHRAN).date() - timedelta(days=self.RETAIN_DAYS)
        records = []
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(
                entry.get("close"), (int, float)
            ):
                continue
            local_timestamp = entry.get("t_tehran") or entry.get("t")
            record_date = str(local_timestamp or "")[:10]
            try:
                parsed_date = date.fromisoformat(record_date)
            except ValueError:
                continue
            if parsed_date < cutoff:
                continue

            records.append(
                {
                    "date": record_date,
                    "date_jalali": entry.get("date_jalali"),
                    "open": entry.get("open"),
                    "high": entry.get("high"),
                    "low": entry.get("low"),
                    "close": float(entry["close"]),
                    "quality": entry.get("quality") or [],
                }
            )
        return records

    def _store(self, symbol: str, records: list[dict], fetched_at: float):
        cutoff = (
            datetime.now(self.TEHRAN).date() - timedelta(days=self.RETAIN_DAYS)
        ).isoformat()
        with self._connect() as db:
            db.execute(
                "DELETE FROM daily_prices WHERE symbol = ? AND date < ?",
                (symbol, cutoff),
            )
            db.executemany(
                """INSERT INTO daily_prices
                   (symbol, date, date_jalali, open, high, low, close, quality)
                   VALUES (:symbol, :date, :date_jalali, :open, :high, :low,
                           :close, :quality)
                   ON CONFLICT(symbol, date) DO UPDATE SET
                       date_jalali = excluded.date_jalali,
                       open = excluded.open,
                       high = excluded.high,
                       low = excluded.low,
                       close = excluded.close,
                       quality = excluded.quality""",
                [
                    {
                        **record,
                        "symbol": symbol,
                        "quality": json.dumps(record["quality"]),
                    }
                    for record in records
                ],
            )
            db.execute(
                """INSERT INTO cache_state (symbol, fetched_at) VALUES (?, ?)
                   ON CONFLICT(symbol) DO UPDATE SET fetched_at = excluded.fetched_at""",
                (symbol, fetched_at),
            )

    def _result(self, records: list[dict], fetched_at: float, stale: bool) -> dict:
        refreshed_at = datetime.fromtimestamp(fetched_at, timezone.utc).astimezone(
            self.TEHRAN
        )
        return {
            "records": records,
            "refreshed_at": refreshed_at.strftime("%d %b %Y, %H:%M"),
            "stale": stale,
        }
