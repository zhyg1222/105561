import json

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
                "trace_id, shadow, status, attempts, last_error FROM app_events "
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

    async def count_outbox(self) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute("SELECT COUNT(*) AS n FROM app_outbox")
            row = await cur.fetchone()
            return int(row["n"])
