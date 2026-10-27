import httpx
import pytest

from xiaojuju_agent.browser import BrowserActionTool, BrowserReadTool
from xiaojuju_agent.context import reset_current_event_id, set_current_event_id
from xiaojuju_agent.policy import PolicyClient
from xiaojuju_agent.tools import ToolExecutor


@pytest.mark.asyncio
async def test_browser_read_is_policy_gated_and_rendered():
    calls = []

    async def allow(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "allow", "reason": "public_read"}},
        )

    def read(url):
        calls.append(url)
        return {"title": "Example", "url": url, "text": "rendered body"}

    tool = BrowserReadTool(
        ToolExecutor(PolicyClient("http://opa", transport=httpx.MockTransport(allow))),
        read,
    )
    result = await tool.read("https://example.com")

    assert result.executed is True
    assert result.result["title"] == "Example"
    assert calls == ["https://example.com"]


class FakeApprovalStore:
    def __init__(self):
        self.created = []

    async def create(self, *, event_id, tool, args):
        self.created.append((event_id, tool, args))
        return {"approval_id": "approval-1"}

    async def consume(self, approval_id, *, event_id, tool, args):
        return approval_id == "approval-1"


@pytest.mark.asyncio
async def test_browser_action_requires_approval_and_can_consume_it():
    async def approval_required(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "require_approval", "reason": "public_publish"}},
        )

    executed = []
    store = FakeApprovalStore()
    tool = BrowserActionTool(
        ToolExecutor(
            PolicyClient("http://opa", transport=httpx.MockTransport(approval_required)),
            approval_store=store,
        ),
        lambda actions: executed.append(actions) or {"ok": True},
    )
    pending = await tool.act(
        [{"action": "click", "selector": "#publish"}],
        event_id="event-browser-action",
    )
    assert pending.executed is False
    assert pending.result["approval_id"] == "approval-1"
    assert executed == []

    done = await tool.act(
        [{"action": "click", "selector": "#publish"}],
        event_id="event-browser-action",
        approval="approval-1",
    )
    assert done.executed is True
    assert len(executed) == 1


def test_browser_action_rejects_private_navigation():
    tool = BrowserActionTool(ToolExecutor(policy_client=None), lambda actions: {})
    with pytest.raises(ValueError, match="public"):
        import asyncio

        asyncio.run(tool.act([{"action": "navigate", "url": "http://127.0.0.1"}]))


@pytest.mark.asyncio
async def test_browser_action_uses_current_event_context():
    async def approval_required(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "require_approval", "reason": "public_publish"}},
        )

    store = FakeApprovalStore()
    tool = BrowserActionTool(
        ToolExecutor(
            PolicyClient("http://opa", transport=httpx.MockTransport(approval_required)),
            approval_store=store,
        )
    )
    token = set_current_event_id("event-context")
    try:
        await tool.act([{"action": "click", "selector": "#publish"}])
    finally:
        reset_current_event_id(token)
    assert store.created[-1][0] == "event-context"
