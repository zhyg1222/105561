import pytest
from httpx import ASGITransport, AsyncClient

from tests.agent.helpers import FakeEventService, IdempotentProcessor
from xiaojuju_agent.api import create_app
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


@pytest.mark.asyncio
async def test_outbox_api_claim_and_ack(event_store):
    from xiaojuju_agent.outbox import OutboxStore

    store = OutboxStore(event_store.db)
    await store.enqueue("owner", "api bridge", message_id="api-outbox-1")
    app = create_app(
        FakeEventService(),
        IdempotentProcessor(),
        lambda event_id: None,
        None,
        force_shadow=False,
        outbox_store=store,
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        claimed = await client.post("/v1/outbox/claim")
        assert claimed.status_code == 200
        message = claimed.json()["message"]
        assert message["message_id"] == "api-outbox-1"
        assert message["status"] == "sending"
        acked = await client.post("/v1/outbox/api-outbox-1/ack")
        assert acked.status_code == 200
        assert (await store.get("api-outbox-1"))["status"] == "sent"
