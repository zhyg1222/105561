import pytest

from xiaojuju_agent.contracts import IncomingEvent


@pytest.mark.asyncio
async def test_event_id_is_idempotent(event_store):
    event = IncomingEvent(
        event_id="event-1",
        source="shadow",
        kind="message",
        contact_id="owner",
        external_id="msg-1",
        payload={"text": "你好"},
        trace_id="trace-1",
        shadow=True,
    )
    assert await event_store.insert_event(event) is True
    assert await event_store.insert_event(event) is False
    stored = await event_store.get_event("event-1")
    assert stored["status"] == "received"
    assert stored["payload"] == {"text": "你好"}
