import asyncio
from datetime import UTC, datetime

import pytest

from xiaojuju_agent.contracts import IncomingEvent


def event(event_id: str = "event-1", **overrides) -> IncomingEvent:
    values = {
        "event_id": event_id,
        "source": "shadow",
        "kind": "message",
        "contact_id": "owner",
        "external_id": f"external-{event_id}",
        "payload": {"text": "hello"},
        "trace_id": f"trace-{event_id}",
        "shadow": True,
        "timestamp": datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC),
    }
    values.update(overrides)
    return IncomingEvent(**values)


@pytest.mark.asyncio
async def test_event_id_is_idempotent(event_store):
    item = event()
    assert await event_store.insert_event(item) is True
    assert await event_store.insert_event(item) is False
    stored = await event_store.get_event("event-1")
    assert stored["status"] == "received"
    assert stored["payload"] == {"text": "hello"}
    assert stored["timestamp"] == item.timestamp


@pytest.mark.asyncio
async def test_event_result_roundtrip(event_store):
    item = event("event-result")
    await event_store.insert_event(item)
    claim = await event_store.claim_event(item.event_id, lease_seconds=60)
    assert claim is not None
    assert await event_store.save_result(
        item.event_id,
        {"reply": "saved"},
        claim_token=claim["claim_token"],
    )
    stored = await event_store.get_event(item.event_id)
    assert stored["status"] == "completed"
    assert stored["result"] == {"reply": "saved"}
    assert stored["claim_token"] is None


@pytest.mark.asyncio
async def test_concurrent_claim_allows_only_one_processor(event_store):
    item = event("claim-once")
    await event_store.insert_event(item)

    claims = await asyncio.gather(
        event_store.claim_event(item.event_id, lease_seconds=60),
        event_store.claim_event(item.event_id, lease_seconds=60),
    )

    winners = [claim for claim in claims if claim is not None]
    assert len(winners) == 1
    assert winners[0]["status"] == "processing"


@pytest.mark.asyncio
async def test_stale_processing_claim_is_recovered(event_store):
    item = event("stale")
    await event_store.insert_event(item)
    first = await event_store.claim_event(item.event_id, lease_seconds=0)
    assert first is not None

    await asyncio.sleep(0.01)
    recovered = await event_store.recover_stale_processing(lease_seconds=0)
    assert recovered == 1
    stored = await event_store.get_event(item.event_id)
    assert stored["status"] == "queued"
    assert stored["claim_token"] is None
