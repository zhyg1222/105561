import httpx
import pytest

from xiaojuju_agent.contracts import PolicyInput
from xiaojuju_agent.policy import PolicyClient
from xiaojuju_agent.tools import MessageSendTool, ToolExecutor


@pytest.mark.asyncio
async def test_side_effect_tool_is_not_called_when_opa_is_unavailable():
    called = []

    async def send_message():
        called.append("hello")
        return {"sent": True}

    async def unavailable(request):
        raise httpx.ConnectError("opa down", request=request)

    executor = ToolExecutor(PolicyClient("http://opa", transport=httpx.MockTransport(unavailable)))
    call = PolicyInput(
        actor="xiaojuju",
        source="wechat",
        tool="message.send",
        args={"text": "hello"},
        contact_id="owner",
        shadow=False,
        side_effect=True,
    )

    result = await executor.execute(call, send_message)

    assert result.executed is False
    assert result.decision.reason == "policy_unavailable"
    assert called == []


@pytest.mark.asyncio
async def test_shadow_side_effect_is_denied_before_execution():
    called = []
    executor = ToolExecutor(policy_client=None)
    call = PolicyInput(
        actor="xiaojuju",
        source="shadow",
        tool="browser.publish",
        args={},
        contact_id="owner",
        shadow=True,
        side_effect=True,
    )

    result = await executor.execute(call, lambda: called.append("published"))

    assert result.executed is False
    assert result.decision.reason == "shadow_side_effect"
    assert called == []


@pytest.mark.asyncio
async def test_message_send_tool_uses_policy_and_idempotent_outbox_id():
    calls = []

    class FakeOutbox:
        async def enqueue(self, contact_id, text, *, kind, message_id):
            calls.append((contact_id, text, kind, message_id))
            return {"message_id": message_id, "status": "queued"}

    async def allow(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "allow", "reason": "owner_message"}},
        )

    outbox = FakeOutbox()
    executor = ToolExecutor(PolicyClient("http://opa", transport=httpx.MockTransport(allow)))
    tool = MessageSendTool(executor, outbox)

    result = await tool.send(
        source="wechat",
        contact_id="owner",
        text="hello",
        event_id="event-42",
    )

    assert result.executed is True
    assert calls == [("owner", "hello", "message", "event-42:send")]


@pytest.mark.asyncio
async def test_message_send_tool_shadow_never_reaches_outbox():
    calls = []

    class FakeOutbox:
        async def enqueue(self, *args, **kwargs):
            calls.append((args, kwargs))

    tool = MessageSendTool(ToolExecutor(policy_client=None), FakeOutbox())
    result = await tool.send(
        source="shadow",
        contact_id="owner",
        text="hello",
        event_id="event-shadow",
        shadow=True,
    )

    assert result.executed is False
    assert calls == []
