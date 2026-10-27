from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from xiaojuju_core.contacts import contact_key

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MemoryCandidate:
    """A durable unit of work for writing one event into memory."""

    event_id: str
    contact_id: str
    user_text: str
    assistant_text: str
    source: str
    group_id: str
    reference_time: datetime
    candidate_id: str = field(default_factory=lambda: uuid.uuid4().hex)


def build_memory_candidate(
    *,
    event_id: str,
    contact: str,
    user_text: str,
    assistant_text: str,
    source: str,
    reference_time: datetime | None = None,
) -> MemoryCandidate:
    when = reference_time or datetime.now(UTC)
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return MemoryCandidate(
        event_id=str(event_id),
        contact_id=str(contact),
        user_text=str(user_text),
        assistant_text=str(assistant_text),
        source=str(source),
        group_id="contact_" + contact_key(contact),
        reference_time=when,
    )


async def insert_memory_candidate(conn, candidate: MemoryCandidate) -> None:
    """Insert a candidate in the caller's transaction.

    Keeping this insert in the same transaction as the event result closes the
    crash window between "event completed" and "memory queued".
    """

    await conn.execute(
        """
        INSERT INTO app_memory_candidates(
            candidate_id, event_id, contact_id, user_text, assistant_text,
            source, group_id, reference_time
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (event_id) DO NOTHING
        """,
        (
            candidate.candidate_id,
            candidate.event_id,
            candidate.contact_id,
            candidate.user_text,
            candidate.assistant_text,
            candidate.source,
            candidate.group_id,
            candidate.reference_time,
        ),
    )


class MemoryQueueStore:
    """Postgres-backed at-least-once queue for memory ingestion.

    The queue is intentionally small and local to the existing platform. It
    does not create a second source of truth: the event result and the queue
    row are committed together, then this worker drains the row to Graphiti.
    """

    _returning_columns = (
        "c.candidate_id, c.event_id, c.contact_id, c.user_text, c.assistant_text, "
        "c.source, c.group_id, c.reference_time, c.status, c.attempts, "
        "c.next_attempt_at, c.claim_token, c.lease_expires_at, c.last_error, "
        "c.created_at, c.updated_at, c.completed_at"
    )

    def __init__(self, db):
        self.db = db

    async def enqueue(self, candidate: MemoryCandidate) -> None:
        async with self.db.transaction() as conn:
            await insert_memory_candidate(conn, candidate)

    async def recover_stale(self) -> int:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_memory_candidates
                SET status='queued', next_attempt_at=now(), claim_token=NULL,
                    lease_expires_at=NULL, updated_at=now()
                WHERE status='processing' AND lease_expires_at <= now()
                """
            )
            return cur.rowcount

    async def claim_next(self, lease_seconds: int = 300) -> dict[str, Any] | None:
        claim_token = uuid.uuid4().hex
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                f"""
                WITH next_candidate AS (
                    SELECT candidate_id
                    FROM app_memory_candidates
                    WHERE status='queued' AND next_attempt_at <= now()
                    ORDER BY created_at, candidate_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                )
                UPDATE app_memory_candidates AS c
                SET status='processing', attempts=c.attempts + 1,
                    claim_token=%s,
                    lease_expires_at=now() + (%s * interval '1 second'),
                    updated_at=now()
                FROM next_candidate
                WHERE c.candidate_id=next_candidate.candidate_id
                RETURNING {self._returning_columns}
                """,
                (claim_token, int(lease_seconds)),
            )
            return await cur.fetchone()

    async def mark_done(self, candidate_id: str, claim_token: str) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_memory_candidates
                SET status='done', completed_at=now(), claim_token=NULL,
                    lease_expires_at=NULL, last_error='', updated_at=now()
                WHERE candidate_id=%s AND status='processing' AND claim_token=%s
                """,
                (str(candidate_id), str(claim_token)),
            )
            return cur.rowcount == 1

    async def mark_retry(
        self,
        candidate_id: str,
        claim_token: str,
        error: str,
        *,
        delay_seconds: int,
    ) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_memory_candidates
                SET status='queued', next_attempt_at=now() + (%s * interval '1 second'),
                    claim_token=NULL, lease_expires_at=NULL, last_error=%s, updated_at=now()
                WHERE candidate_id=%s AND status='processing' AND claim_token=%s
                """,
                (int(delay_seconds), str(error)[:4000], str(candidate_id), str(claim_token)),
            )
            return cur.rowcount == 1

    async def mark_failed(self, candidate_id: str, claim_token: str, error: str) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_memory_candidates
                SET status='failed', completed_at=now(), claim_token=NULL,
                    lease_expires_at=NULL, last_error=%s, updated_at=now()
                WHERE candidate_id=%s AND status='processing' AND claim_token=%s
                """,
                (str(error)[:4000], str(candidate_id), str(claim_token)),
            )
            return cur.rowcount == 1

    async def requeue_failed(self, candidate_id: str) -> bool:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                UPDATE app_memory_candidates
                SET status='queued', next_attempt_at=now(), attempts=0,
                    last_error='', completed_at=NULL, updated_at=now()
                WHERE candidate_id=%s AND status='failed'
                """,
                (str(candidate_id),),
            )
            return cur.rowcount == 1

    async def stats(self) -> dict[str, int]:
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                """
                SELECT status, COUNT(*) AS n
                FROM app_memory_candidates
                GROUP BY status
                """
            )
            rows = await cur.fetchall()
        result = {"queued": 0, "processing": 0, "done": 0, "failed": 0}
        for row in rows:
            result[str(row["status"])] = int(row["n"])
        return result


class MemoryIngestionWorker:
    """Sequential Graphiti ingestion worker used by the standalone process."""

    def __init__(
        self,
        queue: MemoryQueueStore,
        provider,
        *,
        poll_interval_seconds: float = 2.0,
        lease_seconds: int = 300,
        max_attempts: int = 5,
    ):
        self.queue = queue
        self.provider = provider
        self.poll_interval_seconds = max(0.1, float(poll_interval_seconds))
        self.lease_seconds = max(1, int(lease_seconds))
        self.max_attempts = max(1, int(max_attempts))

    async def run_once(self) -> bool:
        await self.queue.recover_stale()
        candidate = await self.queue.claim_next(lease_seconds=self.lease_seconds)
        if candidate is None:
            return False
        candidate_id = str(candidate["candidate_id"])
        claim_token = str(candidate["claim_token"])
        try:
            await self.provider.persist_candidate(candidate)
        except Exception as exc:  # noqa: BLE001 - worker persists and retries failures
            attempts = int(candidate.get("attempts", 1))
            if attempts >= self.max_attempts:
                await self.queue.mark_failed(candidate_id, claim_token, repr(exc))
                logger.error("memory candidate %s exhausted retries: %s", candidate_id, exc)
            else:
                delay = min(300, 10 * (2 ** (attempts - 1)))
                await self.queue.mark_retry(
                    candidate_id,
                    claim_token,
                    repr(exc),
                    delay_seconds=delay,
                )
                logger.warning(
                    "memory candidate %s failed; retrying in %ss: %s",
                    candidate_id,
                    delay,
                    exc,
                )
        else:
            try:
                await self.queue.mark_done(candidate_id, claim_token)
            except Exception:
                logger.exception(
                    "memory candidate %s finished but queue acknowledgement failed",
                    candidate_id,
                )
                raise
        return True

    async def run_forever(self, stop_event: asyncio.Event | None = None) -> None:
        while stop_event is None or not stop_event.is_set():
            try:
                worked = await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("memory ingestion worker loop failed")
                worked = False
            if not worked:
                await asyncio.sleep(self.poll_interval_seconds)
