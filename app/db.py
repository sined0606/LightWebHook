from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class EventStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_db(self) -> None:
        with self.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    webhook_name TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    payload_encoding TEXT NOT NULL,
                    content_type TEXT,
                    headers_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_webhook_events_name_received
                ON webhook_events (webhook_name, received_at DESC)
                """
            )

    def record_event(
        self,
        *,
        webhook_name: str,
        received_at: str,
        payload: str,
        payload_encoding: str,
        content_type: str | None,
        headers: dict[str, str],
    ) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO webhook_events (
                    webhook_name,
                    received_at,
                    payload,
                    payload_encoding,
                    content_type,
                    headers_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    webhook_name,
                    received_at,
                    payload,
                    payload_encoding,
                    content_type,
                    json.dumps(headers, ensure_ascii=True, sort_keys=True),
                ),
            )
            return int(cursor.lastrowid)

    def get_status(self, webhook_name: str) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) AS trigger_count, MAX(received_at) AS last_triggered_at
                FROM webhook_events
                WHERE webhook_name = ?
                """,
                (webhook_name,),
            ).fetchone()

        trigger_count = int(row["trigger_count"]) if row is not None else 0
        last_triggered_at = row["last_triggered_at"] if row is not None else None

        return {
            "webhook": webhook_name,
            "triggered": trigger_count > 0,
            "trigger_count": trigger_count,
            "last_triggered_at": last_triggered_at,
        }

    def list_statuses(self, webhook_names: list[str]) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT webhook_name, COUNT(*) AS trigger_count, MAX(received_at) AS last_triggered_at
                FROM webhook_events
                GROUP BY webhook_name
                """
            ).fetchall()

        status_by_name = {
            row["webhook_name"]: {
                "trigger_count": int(row["trigger_count"]),
                "last_triggered_at": row["last_triggered_at"],
            }
            for row in rows
        }

        statuses: list[dict[str, Any]] = []
        for webhook_name in webhook_names:
            status = status_by_name.get(webhook_name, {})
            trigger_count = int(status.get("trigger_count", 0))
            statuses.append(
                {
                    "webhook": webhook_name,
                    "triggered": trigger_count > 0,
                    "trigger_count": trigger_count,
                    "last_triggered_at": status.get("last_triggered_at"),
                }
            )

        return statuses

    def get_events(self, webhook_name: str, limit: int) -> list[dict[str, Any]]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, received_at, payload, payload_encoding, content_type, headers_json
                FROM webhook_events
                WHERE webhook_name = ?
                ORDER BY received_at DESC, id DESC
                LIMIT ?
                """,
                (webhook_name, limit),
            ).fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            events.append(
                {
                    "id": int(row["id"]),
                    "received_at": row["received_at"],
                    "payload": row["payload"],
                    "payload_encoding": row["payload_encoding"],
                    "content_type": row["content_type"],
                    "headers": json.loads(row["headers_json"]),
                }
            )

        return events

    def reset(self, webhook_name: str) -> int:
        with self.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM webhook_events WHERE webhook_name = ?",
                (webhook_name,),
            )
            return int(cursor.rowcount)
