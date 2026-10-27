import pytest

from xiaojuju_agent.outbox import OutboxStore


@pytest.mark.asyncio
async def test_outbox_enqueue_claim_and_receipt(event_store):
    store = OutboxStore(event_store.db)
    first = await store.enqueue(
        "owner",
        "hello",
        kind="proactive_chat",
        message_id="outbox-1",
    )
    duplicate = await store.enqueue(
        "owner",
        "different text",
        message_id="outbox-1",
    )

    assert first["text"] == "hello"
    assert duplicate["text"] == "hello"
    assert await store.pending_count() == 1

    claimed = await store.claim_next()
    assert claimed["message_id"] == "outbox-1"
    assert claimed["status"] == "sending"
    assert claimed["attempts"] == 1
    assert await store.pending_count() == 1

    await store.mark_sent("outbox-1")
    assert (await store.get("outbox-1"))["status"] == "sent"
    assert await store.pending_count() == 0


@pytest.mark.asyncio
async def test_outbox_failure_requeues_and_can_be_failed(event_store):
    store = OutboxStore(event_store.db)
    await store.enqueue("owner", "retry me", message_id="outbox-2")
    await store.claim_next()
    await store.mark_retry("outbox-2", "temporary")

    retried = await store.claim_next()
    assert retried["attempts"] == 2
    await store.mark_failed("outbox-2", "permanent")
    row = await store.get("outbox-2")
    assert row["status"] == "failed"
    assert row["last_error"] == "permanent"
