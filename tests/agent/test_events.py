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
        external_id="m1",
        payload={"text": "测试"},
        trace_id="t1",
        shadow=True,
    )
    result = await service.submit(event, dispatch=dispatched.append)
    assert result.accepted is True
    assert result.status == "received"
    assert dispatched == []
    assert await event_store.count_outbox() == 0
