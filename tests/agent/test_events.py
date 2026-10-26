from datetime import UTC, datetime

import pytest

from xiaojuju_agent.contracts import IncomingEvent
from xiaojuju_agent.events import EventService


@pytest.mark.asyncio
async def test_shadow_event_is_not_dispatched_or_added_to_outbox(event_store):
    dispatched = []
    service = EventService(event_store)
    event = IncomingEvent(
        event_id="shadow-1",
        source="shadow",
        kind="message",
        contact_id="owner",
        external_id="shadow-message-1",
        payload={"text": "shadow"},
        trace_id="t1",
        shadow=True,
    )

    result = await service.submit(event, dispatch=lambda event_id: dispatched.append(event_id))

    assert result.accepted is True
    assert result.status == "received"
    assert dispatched == []
    assert await event_store.count_outbox() == 0


@pytest.mark.asyncio
async def test_dispatch_failure_is_recoverable_without_losing_event(event_store):
    service = EventService(event_store)
    event = IncomingEvent(
        event_id="queued-after-broker-failure",
        source="live",
        kind="message",
        external_id="live-message-1",
        payload={"text": "hello"},
        trace_id="trace-live",
        shadow=False,
        timestamp=datetime(2020, 1, 2, 3, 4, 5, tzinfo=UTC),
    )

    def broker_down(event_id):
        raise ConnectionError("broker down")

    first = await service.submit(event, dispatch=broker_down)
    stored = await event_store.get_event(event.event_id)

    assert first.accepted is True
    assert stored["status"] == "queued"
    assert stored["published_at"] is None
    assert stored["timestamp"] == event.timestamp

    dispatched = []

    def broker_up(event_id):
        dispatched.append(event_id)

    assert await service.publish_pending(broker_up) == 1
    assert dispatched == [event.event_id]
    assert await service.publish_pending(broker_up) == 0
    assert dispatched == [event.event_id]


@pytest.mark.asyncio
async def test_duplicate_external_id_returns_existing_event(event_store):
    service = EventService(event_store)
    first = IncomingEvent(
        event_id="external-first",
        source="live",
        kind="message",
        external_id="same-external-id",
        payload={"text": "first"},
        trace_id="t1",
        shadow=True,
    )
    second = IncomingEvent(
        event_id="external-second",
        source="live",
        kind="message",
        external_id="same-external-id",
        payload={"text": "second"},
        trace_id="t2",
        shadow=True,
    )

    await service.accept(first)
    duplicate = await service.accept(second)

    assert duplicate.accepted is False
    assert duplicate.status == "received"
    assert duplicate.event_id == first.event_id


@pytest.mark.asyncio
async def test_received_event_is_republished_after_process_restart(event_store):
    event = IncomingEvent(
        event_id="received-before-crash",
        source="live",
        kind="message",
        external_id="crash-message",
        payload={"text": "hello"},
        trace_id="trace-crash",
        shadow=False,
    )
    await event_store.insert_event(event)
    dispatched = []
    service = EventService(event_store)

    assert await service.publish_pending(lambda event_id: dispatched.append(event_id)) == 1
    assert dispatched == [event.event_id]
    assert await service.publish_pending(lambda event_id: dispatched.append(event_id)) == 0
