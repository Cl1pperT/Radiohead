"""SQLite storage for message history and conversation memory."""

from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class MessageRecord:
    direction: str
    sender_id: str
    sender_short_name: Optional[str]
    sender_long_name: Optional[str]
    channel: Optional[int]
    text: str
    timestamp: float
    latency_ms: Optional[float]
    message_id: Optional[str]


class SQLiteStorage:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "meshtastic_llm_bridge.sqlite3"
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    direction TEXT NOT NULL,
                    sender_id TEXT NOT NULL,
                    sender_short_name TEXT,
                    sender_long_name TEXT,
                    channel INTEGER,
                    text TEXT NOT NULL,
                    latency_ms REAL,
                    message_id TEXT
                )
                """
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_sender_time
                ON messages (sender_id, timestamp)
                """
            )

    def add_message(self, record: MessageRecord) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO messages (
                    timestamp,
                    direction,
                    sender_id,
                    sender_short_name,
                    sender_long_name,
                    channel,
                    text,
                    latency_ms,
                    message_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.timestamp,
                    record.direction,
                    record.sender_id,
                    record.sender_short_name,
                    record.sender_long_name,
                    record.channel,
                    record.text,
                    record.latency_ms,
                    record.message_id,
                ),
            )

    def get_recent_messages(self, sender_id: str, limit: int) -> List[MessageRecord]:
        with self._lock:
            cursor = self._conn.execute(
                """
                SELECT * FROM messages
                WHERE sender_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (sender_id, limit),
            )
            rows = cursor.fetchall()
        records = [
            MessageRecord(
                direction=row["direction"],
                sender_id=row["sender_id"],
                sender_short_name=row["sender_short_name"],
                sender_long_name=row["sender_long_name"],
                channel=row["channel"],
                text=row["text"],
                timestamp=row["timestamp"],
                latency_ms=row["latency_ms"],
                message_id=row["message_id"],
            )
            for row in rows
        ]
        return list(reversed(records))

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def now_ts() -> float:
    return time.time()
