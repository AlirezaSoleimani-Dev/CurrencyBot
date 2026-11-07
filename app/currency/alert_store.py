import sqlite3
from datetime import datetime, timezone
from pathlib import Path


class SQLiteAlertStore:
    """Persist one-shot price alerts in the bot's SQLite database."""

    MAX_ACTIVE_PER_USER = 10

    def __init__(self, database_path: str):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        return sqlite3.connect(self.database_path, timeout=10)

    def _initialize(self):
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS price_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    title TEXT NOT NULL,
                    price_label TEXT NOT NULL,
                    target REAL NOT NULL,
                    direction TEXT NOT NULL CHECK(direction IN ('above', 'below')),
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'triggered', 'cancelled')),
                    created_at TEXT NOT NULL,
                    triggered_at TEXT
                )"""
            )
            db.execute(
                """CREATE INDEX IF NOT EXISTS idx_price_alerts_active
                   ON price_alerts(status, symbol)"""
            )

    def create(
        self,
        chat_id: int,
        user_id: int,
        symbol: str,
        title: str,
        price_label: str,
        target: float,
        direction: str,
    ) -> int:
        with self._connect() as db:
            active_count = db.execute(
                """SELECT COUNT(*) FROM price_alerts
                   WHERE chat_id = ? AND user_id = ? AND status = 'active'""",
                (chat_id, user_id),
            ).fetchone()[0]
            if active_count >= self.MAX_ACTIVE_PER_USER:
                raise ValueError(
                    f"You can have at most {self.MAX_ACTIVE_PER_USER} active alerts."
                )
            cursor = db.execute(
                """INSERT INTO price_alerts
                   (chat_id, user_id, symbol, title, price_label, target,
                    direction, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    chat_id,
                    user_id,
                    symbol,
                    title,
                    price_label,
                    target,
                    direction,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            return cursor.lastrowid

    def get_active(self) -> list[dict]:
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT id, chat_id, user_id, symbol, title, price_label,
                          target, direction
                   FROM price_alerts WHERE status = 'active' ORDER BY id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_for_user(self, chat_id: int, user_id: int) -> list[dict]:
        with self._connect() as db:
            db.row_factory = sqlite3.Row
            rows = db.execute(
                """SELECT id, symbol, title, target, direction, created_at
                   FROM price_alerts
                   WHERE chat_id = ? AND user_id = ? AND status = 'active'
                   ORDER BY id""",
                (chat_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def cancel(self, alert_id: int, chat_id: int, user_id: int) -> bool:
        with self._connect() as db:
            cursor = db.execute(
                """UPDATE price_alerts SET status = 'cancelled'
                   WHERE id = ? AND chat_id = ? AND user_id = ? AND status = 'active'""",
                (alert_id, chat_id, user_id),
            )
            return cursor.rowcount == 1

    def mark_triggered(self, alert_id: int) -> None:
        with self._connect() as db:
            db.execute(
                """UPDATE price_alerts
                   SET status = 'triggered', triggered_at = ?
                   WHERE id = ? AND status = 'active'""",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), alert_id),
            )
