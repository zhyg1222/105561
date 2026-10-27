from __future__ import annotations

import uuid
from typing import Any


class OutboxStore:
    """Postgres-backed side-effect queue with claim and receipt semantics."""

    _columns = (
        "message_id, contact_id, text, kind, status, attempts, last_error, created_at, updated_at"
    )

    def __init__(self, db):
        self.db = db

    async def enqueue(
        self,
        contact_id: str,
        text: str,
        *,
        kind: str = "message",
        message_id: str | None = None,
    ) -> dict[str, Any]:
        contact_id = str(contact_id).strip()
        text = str(text).strip()
        if not contact_id or not text:
            raise ValueError("contact_id and text are required")
        message_id = str(message_id or uuid.uuid4().hex)
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO app_outbox(message_id, contact_id, text, kind, status)
                VALUES (%s, %s, %s, %s, 'queued')
                ON CONFLICT (message_id) DO NOTHING
                """,
                (message_id, contact_id, text, kind),
            )
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_outbox WHERE message_id=%s",
                (message_id,),
            )
            row = await cur.fetchone()
        if row is None:
            raise RuntimeError("outbox row unavailable after enqueue")
        return row

    async def get(self, message_id: str) -> dict[str, Any] | None:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_outbox WHERE message_id=%s",
                (str(message_id),),
            )
            return await cur.fetchone()

    async def claim_next(self) -> dict[str, Any] | None:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"""
                SELECT {self._columns} FROM app_outbox
                WHERE status='queued'
                ORDER BY created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """
            )
            row = await cur.fetchone()
            if row is None:
                return None
            await conn.execute(
                """
                UPDATE app_outbox
                SET status='sending', attempts=attempts+1, updated_at=now()
                WHERE message_id=%s
                """,
                (row["message_id"],),
            )
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_outbox WHERE message_id=%s",
                (row["message_id"],),
            )
            return await cur.fetchone()

    async def mark_retry(self, message_id: str, error: str = "") -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_outbox
                SET status='queued', last_error=%s, updated_at=now()
                WHERE message_id=%s AND status IN ('sending','queued')
                """,
                (str(error)[:4000], str(message_id)),
            )

    async def mark_sent(self, message_id: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_outbox
                SET status='sent', last_error='', updated_at=now()
                WHERE message_id=%s AND status='sending'
                """,
                (str(message_id),),
            )

    async def mark_failed(self, message_id: str, error: str = "") -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_outbox
                SET status='failed', last_error=%s, updated_at=now()
                WHERE message_id=%s AND status IN ('sending','queued')
                """,
                (str(error)[:4000], str(message_id)),
            )

    async def recover_stale(self, stale_seconds: int = 120) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_outbox
                SET status='queued', last_error='stale claim recovered', updated_at=now()
                WHERE status='sending' AND updated_at <= now() - (%s * interval '1 second')
                """,
                (int(stale_seconds),),
            )
            return cur.rowcount

    async def pending_count(self) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                "SELECT COUNT(*) AS n FROM app_outbox WHERE status IN ('queued','sending')"
            )
            row = await cur.fetchone()
            return int(row["n"])
