import httpx
import pytest

from xiaojuju_agent.browser import BrowserReadTool
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
