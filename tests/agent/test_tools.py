import httpx
import pytest

from xiaojuju_agent.contracts import PolicyInput
from xiaojuju_agent.policy import PolicyClient
from xiaojuju_agent.tools import ToolExecutor


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
