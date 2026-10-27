import httpx
import pytest

from xiaojuju_agent.policy import PolicyClient
from xiaojuju_agent.tools import ToolExecutor
from xiaojuju_agent.web import WebFetchTool, WebSearchTool, is_public_url


@pytest.mark.asyncio
async def test_web_search_is_policy_gated_and_read_only():
    calls = []

    async def allow(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "allow", "reason": "public_read"}},
        )

    def search(query, max_results):
        calls.append((query, max_results))
        return "result text"

    tool = WebSearchTool(
        ToolExecutor(PolicyClient("http://opa", transport=httpx.MockTransport(allow))),
        search,
    )
    result = await tool.search("open source phone agent", max_results=3)

    assert result.executed is True
    assert result.result == "result text"
    assert calls == [("open source phone agent", 3)]


def test_private_and_local_urls_are_rejected():
    assert is_public_url("https://github.com/example")
    assert not is_public_url("http://127.0.0.1:8080")
    assert not is_public_url("http://192.168.1.4")
    assert not is_public_url("http://localhost")
    assert not is_public_url("http://dev.internal")


@pytest.mark.asyncio
async def test_web_fetch_is_policy_gated():
    calls = []

    async def allow(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "allow", "reason": "public_read"}},
        )

    def fetch(url):
        calls.append(url)
        return "page body"

    tool = WebFetchTool(
        ToolExecutor(PolicyClient("http://opa", transport=httpx.MockTransport(allow))),
        fetch,
    )
    result = await tool.fetch("https://github.com/example")

    assert result.executed is True
    assert result.result == "page body"
    assert calls == ["https://github.com/example"]
