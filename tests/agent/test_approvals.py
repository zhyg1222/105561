import httpx
import pytest

from xiaojuju_agent.approvals import ApprovalStore
from xiaojuju_agent.contracts import IncomingEvent, PolicyInput
from xiaojuju_agent.policy import PolicyClient
from xiaojuju_agent.tools import ToolExecutor


async def add_event(store, event_id):
    await store.insert_event(
        IncomingEvent(
            event_id=event_id,
            source="browser",
            kind="tool_result",
            contact_id="eval",
            payload={},
            trace_id=event_id,
            shadow=True,
        )
    )


@pytest.mark.asyncio
async def test_approval_is_one_time_and_must_match(event_store):
    await add_event(event_store, "event-approval")
    store = ApprovalStore(event_store.db)
    approval = await store.create(
        event_id="event-approval",
        tool="browser.publish",
        args={"url": "https://example.com/post"},
    )
    assert await store.decide(approval["approval_id"], "approved") is True
    assert (
        await store.consume(
            approval["approval_id"],
            event_id="event-approval",
            tool="browser.publish",
            args={"url": "https://example.com/post"},
        )
        is True
    )
    assert (
        await store.consume(
            approval["approval_id"],
            event_id="event-approval",
            tool="browser.publish",
            args={"url": "https://example.com/post"},
        )
        is False
    )


@pytest.mark.asyncio
async def test_approval_mismatch_does_not_consume(event_store):
    await add_event(event_store, "event-approval-2")
    store = ApprovalStore(event_store.db)
    approval = await store.create(
        event_id="event-approval-2",
        tool="browser.publish",
        args={"url": "https://example.com/a"},
    )
    await store.decide(approval["approval_id"], "approved")
    assert (
        await store.consume(
            approval["approval_id"],
            event_id="event-approval-2",
            tool="browser.publish",
            args={"url": "https://example.com/b"},
        )
        is False
    )
    assert (await store.get(approval["approval_id"]))["status"] == "approved"


@pytest.mark.asyncio
async def test_tool_executor_requires_and_consumes_approval(event_store):
    await add_event(event_store, "event-executor")
    store = ApprovalStore(event_store.db)

    async def approval_required(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "require_approval", "reason": "public_publish"}},
        )

    executor = ToolExecutor(
        PolicyClient("http://opa", transport=httpx.MockTransport(approval_required)),
        approval_store=store,
    )
    call = PolicyInput(
        actor="xiaojuju",
        source="browser",
        tool="browser.publish",
        args={"url": "https://example.com/post"},
        event_id="event-executor",
        shadow=False,
        side_effect=True,
    )
    called = []
    first = await executor.execute(call, lambda: called.append("once"))
    assert first.executed is False

    approval = await store.create(
        event_id="event-executor",
        tool="browser.publish",
        args={"url": "https://example.com/post"},
    )
    await store.decide(approval["approval_id"], "approved")
    second = await executor.execute(
        call,
        lambda: called.append("twice"),
        approval=approval["approval_id"],
    )
    assert second.executed is True
    assert called == ["twice"]

    third = await executor.execute(
        call,
        lambda: called.append("three"),
        approval=approval["approval_id"],
    )
    assert third.executed is False
    assert third.decision.reason == "approval_invalid"
