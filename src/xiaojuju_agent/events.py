import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from .contracts import IncomingEvent
from .memory_queue import MemoryCandidate, insert_memory_candidate

logger = logging.getLogger(__name__)


class EventInProgress(RuntimeError):
    """Raised when another worker currently owns the event lease."""


EventProcessing = EventInProgress


@dataclass(frozen=True)
class SubmitResult:
    accepted: bool
    status: str
    shadow: bool
    event_id: str | None = None


class EventStore:
    _columns = (
        "event_id, source, kind, contact_id, external_id, payload, trace_id, "
        "traceparent, timestamp, shadow, result, published_at, claim_token, "
        "lease_expires_at, status, attempts, last_error"
    )

    def __init__(self, db):
        self.db = db

    async def insert_event(self, event: IncomingEvent) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                INSERT INTO app_events(
                    event_id, source, kind, contact_id, external_id,
                    payload, trace_id, traceparent, timestamp, shadow
                ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
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
                    event.traceparent,
                    event.timestamp,
                    event.shadow,
                ),
            )
            return cur.rowcount == 1

    async def get_event(self, event_id: str) -> dict | None:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_events WHERE event_id = %s",
                (event_id,),
            )
            return await cur.fetchone()

    async def get_by_external(self, source: str, external_id: str) -> dict | None:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_events WHERE source = %s AND external_id = %s",
                (source, external_id),
            )
            return await cur.fetchone()

    async def mark_status(self, event_id: str, status: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                "UPDATE app_events SET status=%s, updated_at=now() WHERE event_id=%s",
                (status, event_id),
            )

    async def mark_published(self, event_id: str, traceparent: str = "") -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_events SET published_at=now(), traceparent=%s,
                    updated_at=now() WHERE event_id=%s
                """,
                (traceparent, event_id),
            )

    async def list_unpublished(self, limit: int = 100) -> list[dict]:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"SELECT {self._columns} FROM app_events "
                "WHERE published_at IS NULL AND result IS NULL AND shadow = false "
                "AND status IN ('received', 'queued') ORDER BY created_at LIMIT %s",
                (limit,),
            )
            return list(await cur.fetchall())

    async def claim_event(self, event_id: str, lease_seconds: int = 120) -> dict | None:
        claim_token = uuid.uuid4().hex
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_events
                SET status='processing', attempts=attempts+1,
                    claim_token=%s,
                    lease_expires_at=now() + (%s * interval '1 second'),
                    updated_at=now()
                WHERE event_id=%s AND (
                    status IN ('received','queued')
                    OR (
                        status='processing'
                        AND lease_expires_at <= now()
                    )
                )
                RETURNING claim_token, lease_expires_at, event_id, source, kind,
                    contact_id, external_id, payload, trace_id, traceparent,
                    timestamp, shadow, result, status, attempts, last_error
                """,
                (claim_token, lease_seconds, event_id),
            )
            return await cur.fetchone()

    async def save_result(
        self,
        event_id: str,
        result: dict,
        claim_token: str,
        *,
        memory_candidate: MemoryCandidate | None = None,
    ) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_events
                SET status='completed', result=%s::jsonb, claim_token=NULL,
                    lease_expires_at=NULL, updated_at=now()
                WHERE event_id=%s AND status='processing' AND claim_token=%s
                """,
                (json.dumps(result, ensure_ascii=False), event_id, claim_token),
            )
            saved = cur.rowcount == 1
            if saved and memory_candidate is not None:
                await insert_memory_candidate(conn, memory_candidate)
            return saved

    async def release_claim(self, event_id: str, claim_token: str, error: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_events
                SET status='queued', last_error=%s, claim_token=NULL,
                    lease_expires_at=NULL, updated_at=now()
                WHERE event_id=%s AND status='processing' AND claim_token=%s
                """,
                (error[:4000], event_id, claim_token),
            )

    async def mark_retry(self, event_id: str, error: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_events SET status='queued', last_error=%s,
                    claim_token=NULL, lease_expires_at=NULL, updated_at=now()
                WHERE event_id=%s
                """,
                (error[:4000], event_id),
            )

    async def mark_failed(self, event_id: str, error: str) -> None:
        async with self.db.transaction() as conn:
            await conn.execute(
                """
                UPDATE app_events SET status='failed', last_error=%s,
                    claim_token=NULL, lease_expires_at=NULL, updated_at=now()
                WHERE event_id=%s
                """,
                (error[:4000], event_id),
            )

    async def recover_stale_processing(self, lease_seconds: int = 0) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_events
                SET status='queued', claim_token=NULL, lease_expires_at=NULL,
                    published_at=NULL, updated_at=now()
                WHERE status='processing'
                  AND lease_expires_at <= now() - (%s * interval '1 second')
                """,
                (lease_seconds,),
            )
            return cur.rowcount

    async def count_outbox(self) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute("SELECT COUNT(*) AS n FROM app_outbox")
            row = await cur.fetchone()
            return int(row["n"])


class EventService:
    def __init__(self, store: EventStore):
        self.store = store

    async def accept(self, event: IncomingEvent) -> SubmitResult:
        inserted = await self.store.insert_event(event)
        if inserted:
            return SubmitResult(True, "received", event.shadow, event.event_id)
        existing = await self.store.get_event(event.event_id)
        if existing is None and event.external_id:
            existing = await self.store.get_by_external(event.source, event.external_id)
        if existing is None:
            raise RuntimeError("event conflict without stored event")
        return SubmitResult(
            False, existing["status"], bool(existing["shadow"]), existing["event_id"]
        )

    async def submit(
        self,
        event: IncomingEvent,
        dispatch: Callable[[str], None],
    ) -> SubmitResult:
        accepted = await self.accept(event)
        if accepted.shadow:
            return accepted
        stored = await self.store.get_event(accepted.event_id)
        if stored["status"] in {"completed", "processing", "failed", "denied"}:
            return accepted
        if stored["status"] == "received":
            await self.store.mark_status(accepted.event_id, "queued")
        if stored["published_at"] is None:
            try:
                dispatch(accepted.event_id)
            except Exception:  # noqa: BLE001 - publish_pending retries broker failures
                return SubmitResult(accepted.accepted, "queued", False, accepted.event_id)
            await self.store.mark_published(accepted.event_id, stored["traceparent"])
        return SubmitResult(accepted.accepted, "queued", False, accepted.event_id)

    async def publish_pending(self, dispatch: Callable[[str], None], limit: int = 100) -> int:
        await self.store.recover_stale_processing()
        published = 0
        for event in await self.store.list_unpublished(limit):
            try:
                dispatch(event["event_id"])
            except Exception:
                logger.warning("event publish failed: %s", event["event_id"], exc_info=True)
                continue
            await self.store.mark_published(event["event_id"], event["traceparent"])
            published += 1
        return published
