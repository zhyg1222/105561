import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path


DEFAULT_PRIORITIES = {
    "user": 100,
    "wechat.message": 100,
    "live.message": 80,
    "proactive_chat": 30,
    "timer": 20,
    "autonomy.task": 20,
    "research": 10,
    "research.result": 10,
}


class EventBus:
    """Persistent retryable event queue backed by SQLite.

    Claims are exclusive. A worker should call complete() after successful
    handling and fail() after an error. Requeued events retain attempt counts
    and are never inserted twice for the same event_id.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.path), timeout=30, check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS bus_events (
                    event_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    priority INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'queued',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    created_epoch REAL NOT NULL,
                    updated_epoch REAL NOT NULL,
                    available_epoch REAL NOT NULL,
                    claimed_epoch REAL,
                    completed_epoch REAL,
                    last_error TEXT NOT NULL DEFAULT '',
                    result TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_bus_claim
                    ON bus_events(status, available_epoch, priority DESC, created_epoch);
                CREATE INDEX IF NOT EXISTS idx_bus_topic_status
                    ON bus_events(topic, status);
                """
            )

    def _require_open(self) -> None:
        if self._conn is None:
            raise RuntimeError("event bus is closed")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def enqueue(
        self,
        key: str,
        topic: str,
        payload: dict | None = None,
        *,
        priority: int | None = None,
        event_id: str | None = None,
        available_at: float | None = None,
    ) -> bool:
        self._require_open()
        event_id = str(event_id or key or "").strip()
        topic = str(topic or "").strip()
        if not event_id:
            raise ValueError("event_id or key is required")
        if not topic:
            raise ValueError("topic is required")
        if payload is not None and not isinstance(payload, dict):
            raise ValueError("payload must be an object")
        if priority is None:
            priority = DEFAULT_PRIORITIES.get(topic, 0)
        now = time.time()
        available = now if available_at is None else float(available_at)
        payload_text = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO bus_events(
                    event_id, topic, payload, priority, status, attempts,
                    created_epoch, updated_epoch, available_epoch
                ) VALUES (?, ?, ?, ?, 'queued', 0, ?, ?, ?)
                """,
                (event_id, topic, payload_text, int(priority), now, now, available),
            )
        return cur.rowcount == 1

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        try:
            item["payload"] = json.loads(item.get("payload") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["payload"] = {}
        if item.get("result") is not None:
            try:
                item["result"] = json.loads(item["result"])
            except (TypeError, json.JSONDecodeError):
                pass
        return item

    def get(self, event_id: str) -> dict | None:
        self._require_open()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM bus_events WHERE event_id = ?", (str(event_id),)
            ).fetchone()
        return self._decode(row)

    def _claim_where(self, where_sql: str, params: tuple) -> dict | None:
        self._require_open()
        now = time.time()
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute(
                    f"""
                    SELECT * FROM bus_events
                    WHERE {where_sql}
                    ORDER BY priority DESC, created_epoch ASC
                    LIMIT 1
                    """,
                    params,
                ).fetchone()
                if row is None:
                    self._conn.commit()
                    return None
                updated = self._conn.execute(
                    """
                    UPDATE bus_events
                    SET status = 'processing', claimed_epoch = ?, updated_epoch = ?
                    WHERE event_id = ? AND status = 'queued'
                    """,
                    (now, now, row["event_id"]),
                )
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        if updated.rowcount != 1:
            return None
        return self.get(row["event_id"])

    def claim_next(self, now: float | None = None, stale_after: float | None = None) -> dict | None:
        if stale_after is not None:
            self.requeue_stale(stale_after, now=now)
        at = time.time() if now is None else float(now)
        return self._claim_where(
            "status = 'queued' AND available_epoch <= ?", (at,)
        )

    def claim(self, event_id: str, now: float | None = None) -> dict | None:
        at = time.time() if now is None else float(now)
        return self._claim_where(
            "event_id = ? AND status = 'queued' AND available_epoch <= ?",
            (str(event_id), at),
        )

    def requeue_stale(self, stale_after: float, now: float | None = None) -> int:
        self._require_open()
        at = time.time() if now is None else float(now)
        cutoff = at - max(1.0, float(stale_after))
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                UPDATE bus_events
                SET status = 'queued',
                    attempts = attempts + 1,
                    available_epoch = ?,
                    updated_epoch = ?,
                    last_error = CASE
                        WHEN last_error = '' THEN 'claim expired'
                        ELSE last_error
                    END
                WHERE status = 'processing' AND claimed_epoch < ?
                """,
                (at, at, cutoff),
            )
        return cur.rowcount

    def complete(self, event_id: str, result: dict | None = None) -> dict:
        self._require_open()
        now = time.time()
        result_text = None if result is None else json.dumps(result, ensure_ascii=False, sort_keys=True)
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                UPDATE bus_events
                SET status = 'completed', completed_epoch = ?, updated_epoch = ?,
                    last_error = '', result = COALESCE(?, result)
                WHERE event_id = ?
                """,
                (now, now, result_text, str(event_id)),
            )
        if cur.rowcount == 0:
            raise KeyError(event_id)
        return self.get(event_id) or {}

    def fail(
        self,
        event_id: str,
        error: str,
        retry: bool = True,
        max_attempts: int = 5,
        retry_delay: float = 0.0,
    ) -> dict:
        self._require_open()
        current = self.get(event_id)
        if current is None:
            raise KeyError(event_id)
        attempts = int(current.get("attempts", 0)) + 1
        should_retry = bool(retry) and attempts < max(1, int(max_attempts))
        status = "queued" if should_retry else "failed"
        now = time.time()
        available = now + max(0.0, float(retry_delay)) if should_retry else now
        with self._lock, self._conn:
            self._conn.execute(
                """
                UPDATE bus_events
                SET status = ?, attempts = ?, last_error = ?, updated_epoch = ?,
                    available_epoch = ?, claimed_epoch = NULL
                WHERE event_id = ?
                """,
                (status, attempts, str(error)[:4000], now, available, str(event_id)),
            )
        return self.get(event_id) or {}

    def stats(self) -> dict:
        self._require_open()
        with self._lock:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) AS n FROM bus_events GROUP BY status"
            ).fetchall()
        counts = {str(row["status"]): int(row["n"]) for row in rows}
        counts["total"] = sum(counts.values())
        counts.setdefault("queued", 0)
        counts.setdefault("processing", 0)
        counts.setdefault("completed", 0)
        counts.setdefault("failed", 0)
        return counts
