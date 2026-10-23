"""
Хранилище подписчиков каналов уведомлений и журнала доставок.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, List, Optional
from app.config import settings, BASE_DIR


class NotificationStore:
    """SQLite-хранилище подписчиков (Telegram-чаты, каналы) и истории доставок."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            data_dir = BASE_DIR / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(data_dir / "notifications.db")
        else:
            self.db_path = db_path
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self.lock = threading.Lock()
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        with self.lock, self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS subscribers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                title TEXT,
                kind TEXT,
                min_severity TEXT DEFAULT 'low',
                active INTEGER DEFAULT 1,
                added_by TEXT,
                added_ts REAL,
                UNIQUE(channel, chat_id)
            );
            CREATE TABLE IF NOT EXISTS deliveries(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                chat_id TEXT NOT NULL,
                message_id TEXT,
                kind TEXT,
                ok INTEGER,
                error TEXT,
                sent_ts REAL,
                latency_ms REAL
            );
            CREATE INDEX IF NOT EXISTS ix_del_ev ON deliveries(event_id);
            """)
            conn.commit()

    def _rows(self, sql: str, args: tuple = ()) -> List[dict]:
        with self.lock, self._get_connection() as conn:
            cursor = conn.execute(sql, args)
            return [dict(row) for row in cursor.fetchall()]

    def upsert_subscriber(
        self,
        channel: str,
        chat_id: str | int,
        title: str,
        kind: str,
        added_by: Optional[str] = None,
    ) -> dict:
        cid_str = str(chat_id)
        now = time.time()
        with self.lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO subscribers(channel, chat_id, title, kind, added_by, added_ts)
                VALUES(?, ?, ?, ?, ?, ?)
                ON CONFLICT(channel, chat_id) DO UPDATE SET
                    active = 1,
                    title = excluded.title,
                    kind = excluded.kind
                """,
                (channel, cid_str, title, kind, added_by, now),
            )
            conn.commit()
        return self.get_subscriber(channel, cid_str)

    def get_subscriber(self, channel: str, chat_id: str | int) -> Optional[dict]:
        rows = self._rows(
            "SELECT * FROM subscribers WHERE channel = ? AND chat_id = ?",
            (channel, str(chat_id)),
        )
        return rows[0] if rows else None

    def list_subscribers(
        self,
        channel: Optional[str] = None,
        active: Optional[bool] = None,
    ) -> List[dict]:
        where, args = [], []
        if channel:
            where.append("channel = ?")
            args.append(channel)
        if active is not None:
            where.append("active = ?")
            args.append(1 if active else 0)

        clause = (" WHERE " + " AND ".join(where)) if where else ""
        return self._rows(f"SELECT * FROM subscribers{clause} ORDER BY id ASC", tuple(args))

    def update_subscriber(self, subscriber_id: int, **fields: Any) -> None:
        allowed = {"active", "min_severity", "title"}
        valid_fields = {k: v for k, v in fields.items() if k in allowed}
        if not valid_fields:
            return

        cols = [f"{k} = ?" for k in valid_fields.keys()]
        vals = [int(v) if k == "active" else v for k, v in valid_fields.items()]
        vals.append(subscriber_id)

        with self.lock, self._get_connection() as conn:
            conn.execute(f"UPDATE subscribers SET {', '.join(cols)} WHERE id = ?", tuple(vals))
            conn.commit()

    def set_subscriber_active(self, channel: str, chat_id: str | int, active: bool) -> None:
        with self.lock, self._get_connection() as conn:
            conn.execute(
                "UPDATE subscribers SET active = ? WHERE channel = ? AND chat_id = ?",
                (1 if active else 0, channel, str(chat_id)),
            )
            conn.commit()

    def delete_subscriber(self, subscriber_id: int) -> None:
        with self.lock, self._get_connection() as conn:
            conn.execute("DELETE FROM subscribers WHERE id = ?", (subscriber_id,))
            conn.commit()

    def add_delivery(
        self,
        event_id: str | int,
        channel: str,
        chat_id: str | int,
        message_id: Optional[str | int],
        kind: str,
        ok: bool,
        error: Optional[str] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        with self.lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO deliveries(event_id, channel, chat_id, message_id, kind, ok, error, sent_ts, latency_ms)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(event_id),
                    channel,
                    str(chat_id),
                    str(message_id) if message_id is not None else None,
                    kind,
                    1 if ok else 0,
                    error,
                    time.time(),
                    latency_ms,
                ),
            )
            conn.commit()

    def get_deliveries_for_event(self, event_id: str | int, channel: Optional[str] = None) -> List[dict]:
        if channel:
            return self._rows(
                "SELECT * FROM deliveries WHERE event_id = ? AND channel = ? AND ok = 1",
                (str(event_id), channel),
            )
        return self._rows(
            "SELECT * FROM deliveries WHERE event_id = ? AND ok = 1",
            (str(event_id),),
        )

    def delivery_stats(self) -> dict:
        stats: Dict[str, dict] = {}
        for row in self._rows(
            "SELECT channel, ok, COUNT(*) as cnt, AVG(latency_ms) as avg_lat FROM deliveries GROUP BY channel, ok"
        ):
            ch = row["channel"]
            sub = stats.setdefault(ch, {"ok": 0, "failed": 0, "avg_latency_ms": 0.0})
            if row["ok"] == 1:
                sub["ok"] = row["cnt"]
                sub["avg_latency_ms"] = round(row["avg_lat"] or 0.0, 1)
            else:
                sub["failed"] = row["cnt"]
        return stats
