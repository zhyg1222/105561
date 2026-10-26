import json
from collections.abc import Callable
from dataclasses import dataclass

from .contracts import IncomingEvent


class EventStore:
    def __init__(self, db):
        self.db = db

    async def insert_event(self, event: IncomingEvent) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                INSERT INTO app_events(
                    event_id, source, kind, contact_id, external_id,
                    payload, trace_id, shadow
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (
                    event.event_id,
                    event.source,
                    event.kind,
                    event.contact_id,
                    event.external_id,
                    json.dumps(event.payload, ensure_ascii=False),
                    event.trace_id,
                    event.shadow,
                ),
            )
            return cur.rowcount == 1

    async def get_event(self, event_id: str) -> dict | None:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                "SELECT event_id, source, kind, contact_id, external_id, payload, "
                "trace_id, shadow, result, status, attempts, last_error FROM app_events "
                "WHERE event_id = %s",
                (event_id,),
            )
            return await cur.fetchone()

    async def mark_status(self, event_id: str, status: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE app_events SET status=%s, updated_at=now() WHERE event_id=%s",
                (status, event_id),
            )

    async def mark_failed(self, event_id: str, error: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_events SET status='failed', attempts=attempts+1,
                    last_error=%s, updated_at=now() WHERE event_id=%s
                """,
                (error[:4000], event_id),
            )

    async def save_result(self, event_id: str, result: dict) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_events SET status='completed', result=%s::jsonb,
                    updated_at=now() WHERE event_id=%s
                """,
                (json.dumps(result, ensure_ascii=False), event_id),
            )

    async def count_outbox(self) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute("SELECT COUNT(*) AS n FROM app_outbox")
            row = await cur.fetchone()
            return int(row["n"])


@dataclass(frozen=True)
class SubmitResult:
    accepted: bool
    status: str
    shadow: bool


class EventService:
    def __init__(self, store: EventStore):
        self.store = store

    async def submit(self, event: IncomingEvent, dispatch: Callable[[str], None]) -> SubmitResult:
        inserted = await self.store.insert_event(event)
        if not inserted:
            existing = await self.store.get_event(event.event_id)
            if existing is None:
                raise RuntimeError("event insert conflict without a stored event")
            return SubmitResult(False, existing["status"], bool(existing["shadow"]))
        if not event.shadow:
            await self.store.mark_status(event.event_id, "queued")
            dispatch(event.event_id)
            return SubmitResult(True, "queued", False)
        return SubmitResult(True, "received", True)
