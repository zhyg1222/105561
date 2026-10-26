import httpx
import pytest

from xiaojuju_agent.contracts import PolicyInput
from xiaojuju_agent.policy import PolicyClient


@pytest.mark.asyncio
async def test_policy_timeout_fails_closed():
    async def timeout(request):
        raise httpx.ConnectTimeout("down", request=request)

    client = PolicyClient("http://opa", transport=httpx.MockTransport(timeout))
    result = await client.decision(
        PolicyInput(
            actor="xiaojuju",
            source="wechat",
            tool="message.send",
            args={"text": "hi"},
            contact_id="owner",
            shadow=False,
        )
    )
    assert result.effect == "deny"
    assert result.reason == "policy_unavailable"


@pytest.mark.asyncio
async def test_policy_parses_allow_and_approval():
    async def allow(request):
        return httpx.Response(
            200,
            request=request,
            json={"result": {"effect": "allow", "reason": "public_read"}},
        )

    client = PolicyClient("http://opa", transport=httpx.MockTransport(allow))
    result = await client.decision(
        PolicyInput(actor="xiaojuju", source="autonomy", tool="web.search", args={})
    )
    assert result.effect == "allow"
    assert result.reason == "public_read"
