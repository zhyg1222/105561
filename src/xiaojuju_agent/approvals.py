from __future__ import annotations

import json
import uuid
from typing import Any


class ApprovalStore:
    """One-time, expiring approvals for side-effect tools."""

    _columns = "approval_id, event_id, tool, args, status, expires_at, created_at"

    def __init__(self, db):
        self.db = db

    async def create(
        self,
        *,
        event_id: str | None,
        tool: str,
        args: dict[str, Any],
        ttl_seconds: int = 600,
    ) -> dict[str, Any]:
        approval_id = uuid.uuid4().hex
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO app_approvals(approval_id, event_id, tool, args, status, expires_at)
                VALUES (%s, %s, %s, %s::jsonb, 'pending', now() + (%s * interval '1 second'))
                """,
                (
                    approval_id,
                    event_id,
                    tool,
                    json.dumps(args, ensure_ascii=False),
                    int(ttl_seconds),
                ),
            )
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_approvals WHERE approval_id=%s",
                (approval_id,),
            )
            row = await cur.fetchone()
        if row is None:
            raise RuntimeError("approval row unavailable after create")
        return row

    async def get(self, approval_id: str) -> dict[str, Any] | None:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_approvals WHERE approval_id=%s",
                (str(approval_id),),
            )
            return await cur.fetchone()

    async def list_pending(self, limit: int = 20) -> list[dict[str, Any]]:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_approvals WHERE status='pending' ORDER BY created_at LIMIT %s",
                (int(limit),),
            )
            return list(await cur.fetchall())

    async def decide(self, approval_id: str, status: str) -> bool:
        if status not in {"approved", "rejected"}:
            raise ValueError("status must be approved or rejected")
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_approvals
                SET status=%s
                WHERE approval_id=%s AND status='pending' AND expires_at > now()
                """,
                (status, str(approval_id)),
            )
            return cur.rowcount == 1

    async def consume(
        self,
        approval_id: str,
        *,
        event_id: str | None,
        tool: str,
        args: dict[str, Any],
    ) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_approvals
                SET status='consumed'
                WHERE approval_id=%s AND status='approved' AND expires_at > now()
                  AND event_id IS NOT DISTINCT FROM %s
                  AND tool=%s
                  AND args=%s::jsonb
                """,
                (
                    str(approval_id),
                    event_id,
                    str(tool),
                    json.dumps(args, ensure_ascii=False),
                ),
            )
            return cur.rowcount == 1
