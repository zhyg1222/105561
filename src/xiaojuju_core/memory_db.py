import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path


def memory_tokens(text: str) -> set[str]:
    """Small deterministic token set suitable for Chinese and ASCII recall."""
    text = (text or "").lower()
    tokens = set(re.findall(r"[a-z0-9_]{2,}", text))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.add(run)
        tokens.update(run[i:i + 2] for i in range(max(0, len(run) - 1)))
    return {token for token in tokens if token}


class MemoryStore:
    """SQLite-backed long-term memory with contact isolation.

    The store deliberately keeps retrieval deterministic and local. Event text
    remains readable in SQLite, while token rows provide fast candidate recall
    without requiring an external embedding service.
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
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS memory_events (
                    event_id TEXT PRIMARY KEY,
                    contact TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT '',
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL,
                    epoch REAL NOT NULL,
                    importance INTEGER NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );
                CREATE INDEX IF NOT EXISTS idx_memory_contact_epoch
                    ON memory_events(contact, epoch DESC);
                CREATE TABLE IF NOT EXISTS memory_tokens (
                    event_id TEXT NOT NULL,
                    token TEXT NOT NULL,
                    PRIMARY KEY(event_id, token),
                    FOREIGN KEY(event_id) REFERENCES memory_events(event_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_memory_token
                    ON memory_tokens(token, event_id);
                CREATE TABLE IF NOT EXISTS relationships (
                    contact TEXT PRIMARY KEY,
                    familiarity INTEGER NOT NULL DEFAULT 0,
                    trust INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    updated_epoch REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memory_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            self._conn.execute(
                "INSERT OR IGNORE INTO memory_metadata(key, value) VALUES('schema_version', '1')"
            )

    def _require_open(self) -> None:
        if self._conn is None:
            raise RuntimeError("memory store is closed")

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def add_event(
        self,
        event_id: str,
        contact: str,
        source: str,
        user_text: str,
        assistant_text: str,
        *,
        timestamp: str | None = None,
        epoch: float | None = None,
        importance: int = 0,
        metadata: dict | None = None,
    ) -> bool:
        self._require_open()
        contact = str(contact or "").strip()
        if not contact:
            raise ValueError("contact is required")
        event_id = str(event_id or "").strip() or uuid.uuid4().hex
        user_text = str(user_text or "")
        assistant_text = str(assistant_text or "")
        if not user_text and not assistant_text:
            raise ValueError("at least one memory text is required")
        timestamp = timestamp or time.strftime("%Y-%m-%d %H:%M:%S")
        epoch = time.time() if epoch is None else float(epoch)
        token_source = " ".join((user_text, assistant_text))
        tokens = sorted(memory_tokens(token_source))
        metadata_text = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True)

        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT OR IGNORE INTO memory_events(
                    event_id, contact, source, user_text, assistant_text,
                    timestamp, epoch, importance, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    contact,
                    str(source or ""),
                    user_text,
                    assistant_text,
                    timestamp,
                    epoch,
                    int(importance),
                    metadata_text,
                ),
            )
            if cur.rowcount == 0:
                return False
            self._conn.executemany(
                "INSERT OR IGNORE INTO memory_tokens(event_id, token) VALUES (?, ?)",
                ((event_id, token) for token in tokens),
            )
        return True

    @staticmethod
    def _decode_row(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        item = dict(row)
        try:
            item["metadata"] = json.loads(item.get("metadata") or "{}")
        except (TypeError, json.JSONDecodeError):
            item["metadata"] = {}
        item["user"] = item.get("user_text", "")
        item["assistant"] = item.get("assistant_text", "")
        item["time"] = item.get("timestamp", "")
        return item

    def get_event(self, event_id: str) -> dict | None:
        self._require_open()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memory_events WHERE event_id = ?", (str(event_id),)
            ).fetchone()
        return self._decode_row(row)

    def retrieve(self, contact: str, query: str, limit: int = 5) -> list[dict]:
        self._require_open()
        contact = str(contact or "").strip()
        if not contact:
            raise ValueError("contact is required")
        limit = max(1, min(int(limit), 50))
        query_tokens = memory_tokens(query)
        with self._lock:
            relationship = self.relationship(contact)
            rows = self._conn.execute(
                """
                SELECT * FROM memory_events
                WHERE contact = ?
                ORDER BY epoch DESC
                LIMIT 2000
                """,
                (contact,),
            ).fetchall()

        scored = []
        for index, row in enumerate(rows):
            item = self._decode_row(row) or {}
            text = (item.get("user_text", "") + " " + item.get("assistant_text", "")).strip()
            overlap = query_tokens & memory_tokens(text)
            relevance = sum(min(4, max(1, len(token))) for token in overlap)
            importance = int(item.get("importance", 0))
            age_days = max(0.0, (time.time() - float(item.get("epoch", 0))) / 86400)
            recency = max(0.0, 1.5 - age_days / 30)
            relationship_bonus = (
                int(relationship.get("familiarity", 0))
                + int(relationship.get("trust", 0))
            ) / 200
            score = relevance * 4 + importance + recency + relationship_bonus
            item["score"] = round(score, 4)
            item["match_tokens"] = sorted(overlap)
            # Keep two recent memories available even when the wording does not
            # overlap, so ordinary conversation still has continuity.
            if relevance > 0 or index < 2 or not query_tokens:
                scored.append(item)
        scored.sort(key=lambda item: (item["score"], float(item.get("epoch", 0))), reverse=True)
        return scored[:limit]

    def event_count(self, contact: str) -> int:
        self._require_open()
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM memory_events WHERE contact = ?",
                (str(contact),),
            ).fetchone()
        return int(row["n"])

    def update_relationship(
        self,
        contact: str,
        *,
        familiarity: int | None = None,
        trust: int | None = None,
        notes: str | None = None,
    ) -> dict:
        self._require_open()
        contact = str(contact or "").strip()
        if not contact:
            raise ValueError("contact is required")
        current = self.relationship(contact)
        if familiarity is not None:
            current["familiarity"] = max(0, min(100, int(familiarity)))
        if trust is not None:
            current["trust"] = max(0, min(100, int(trust)))
        if notes is not None:
            current["notes"] = str(notes)
        current["updated_epoch"] = time.time()
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO relationships(contact, familiarity, trust, notes, updated_epoch)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(contact) DO UPDATE SET
                    familiarity = excluded.familiarity,
                    trust = excluded.trust,
                    notes = excluded.notes,
                    updated_epoch = excluded.updated_epoch
                """,
                (
                    contact,
                    current["familiarity"],
                    current["trust"],
                    current["notes"],
                    current["updated_epoch"],
                ),
            )
        return current

    def relationship(self, contact: str) -> dict:
        self._require_open()
        contact = str(contact or "").strip()
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM relationships WHERE contact = ?", (contact,)
            ).fetchone()
        if row is None:
            return {
                "contact": contact,
                "familiarity": 0,
                "trust": 0,
                "notes": "",
                "updated_epoch": 0.0,
            }
        return dict(row)

    def migrate_jsonl(self, path: Path | str) -> int:
        self._require_open()
        source_path = Path(path)
        if not source_path.exists():
            return 0
        inserted = 0
        for line in source_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            contact = str(row.get("contact") or "\u5927\u54e5").strip()
            user_text = str(row.get("user", row.get("user_text", "")) or "")
            assistant_text = str(row.get("assistant", row.get("assistant_text", "")) or "")
            if not user_text and not assistant_text:
                continue
            epoch = float(row.get("epoch") or time.time())
            timestamp = str(row.get("time") or row.get("timestamp") or "")
            if not timestamp:
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))
            identity = "\x1f".join((contact, str(epoch), user_text, assistant_text))
            event_id = str(row.get("event_id") or "").strip()
            if not event_id:
                event_id = "jsonl:" + hashlib.sha1(identity.encode("utf-8")).hexdigest()
            if self.add_event(
                event_id,
                contact,
                str(row.get("source") or "jsonl"),
                user_text,
                assistant_text,
                timestamp=timestamp,
                epoch=epoch,
                importance=int(row.get("importance", 0) or 0),
                metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
            ):
                inserted += 1
        return inserted
