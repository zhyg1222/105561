from datetime import UTC, datetime

import pytest

from xiaojuju_agent.contracts import IncomingEvent
from xiaojuju_agent.memory_queue import (
    MemoryIngestionWorker,
    MemoryQueueStore,
    build_memory_candidate,
)


def event(event_id: str = "memory-event") -> IncomingEvent:
    return IncomingEvent(
        event_id=event_id,
        source="wechat",
        kind="message",
        contact_id="owner",
        payload={"text": "hello"},
        trace_id="trace-memory",
    )


async def clear_candidates(db) -> None:
    async with db.transaction() as conn:
        await conn.execute("TRUNCATE app_memory_candidates")


async def insert_candidate(queue: MemoryQueueStore, event_id: str = "memory-event"):
    await queue.enqueue(
        build_memory_candidate(
            event_id=event_id,
            contact="owner",
            user_text="hello",
            assistant_text="world",
            source="wechat",
            reference_time=datetime.now(UTC),
        )
    )


class FakeProvider:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.candidates = []

    async def persist_candidate(self, candidate):
        self.candidates.append(candidate)
        if self.fail:
            raise RuntimeError("graph unavailable")


@pytest.mark.asyncio
async def test_event_result_and_memory_candidate_commit_together(event_store):
    await clear_candidates(event_store.db)
    await event_store.insert_event(event("atomic-event"))
    claim = await event_store.claim_event("atomic-event")
    assert claim is not None
    queue = MemoryQueueStore(event_store.db)
    candidate = build_memory_candidate(
        event_id="atomic-event",
        contact="owner",
        user_text="hello",
        assistant_text="world",
        source="wechat",
        reference_time=claim["timestamp"],
    )

    saved = await event_store.save_result(
        "atomic-event",
        {"reply": "world"},
        claim["claim_token"],
        memory_candidate=candidate,
    )

    assert saved is True
    stats = await queue.stats()
    assert stats["queued"] == 1
    stored = await event_store.get_event("atomic-event")
    assert stored is not None and stored["status"] == "completed"


@pytest.mark.asyncio
async def test_memory_worker_claims_once_and_marks_done(event_store):
    await clear_candidates(event_store.db)
    await event_store.insert_event(event("worker-event"))
    queue = MemoryQueueStore(event_store.db)
    await insert_candidate(queue, "worker-event")
    provider = FakeProvider()
    worker = MemoryIngestionWorker(queue, provider, max_attempts=3)

    assert await worker.run_once() is True
    assert len(provider.candidates) == 1
    assert (await queue.stats())["done"] == 1
    assert await worker.run_once() is False
    async with event_store.db.transaction() as conn:
        cur = await conn.execute(
            "SELECT last_error FROM app_memory_candidates WHERE event_id='worker-event'"
        )
        assert (await cur.fetchone())["last_error"] == ""
    assert (await queue.stats())["done"] == 1


@pytest.mark.asyncio
async def test_memory_worker_retries_then_marks_failed_at_limit(event_store):
    await clear_candidates(event_store.db)
    await event_store.insert_event(event("retry-event"))
    queue = MemoryQueueStore(event_store.db)
    await insert_candidate(queue, "retry-event")
    worker = MemoryIngestionWorker(queue, FakeProvider(fail=True), max_attempts=1)

    assert await worker.run_once() is True
    stats = await queue.stats()
    assert stats["failed"] == 1
    assert stats["queued"] == 0
