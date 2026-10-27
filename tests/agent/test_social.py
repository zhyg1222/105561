from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from tests.agent.helpers import FakeEventService, IdempotentProcessor
from xiaojuju_agent.api import create_app
from xiaojuju_agent.approvals import ApprovalStore
from xiaojuju_agent.contracts import IncomingEvent
from xiaojuju_agent.policy import PolicyClient, PolicyDecision
from xiaojuju_agent.social import SocialPublishRequest, SocialPublishTool, build_publish_spec
from xiaojuju_agent.tools import ToolExecution, ToolExecutor


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def publish(self, spec, *, event_id):
        self.calls.append((spec, event_id))
        return {"status": "published", "verified": True, "receipt_path": "receipt.json"}


async def approval_required(request):
    return httpx.Response(
        200,
        request=request,
        json={"result": {"effect": "require_approval", "reason": "public_publish"}},
    )


async def add_event(event_store, event_id: str):
    await event_store.insert_event(
        IncomingEvent(
            event_id=event_id,
            source="browser",
            kind="tool_result",
            contact_id="owner",
            payload={},
            trace_id=event_id,
            shadow=False,
        )
    )


@pytest.mark.asyncio
async def test_social_publish_requires_approval_and_labels_ai_identity(tmp_path, event_store):
    image = tmp_path / "post.png"
    image.write_bytes(b"not-a-real-image")
    await add_event(event_store, "social-event")
    store = ApprovalStore(event_store.db)
    provider = FakeProvider()
    tool = SocialPublishTool(
        ToolExecutor(PolicyClient("http://opa", transport=httpx.MockTransport(approval_required)), store),
        provider,
        media_root=tmp_path,
        identity_label="[AI]",
    )
    request = SocialPublishRequest(
        platform="xiaohongshu",
        account="creator",
        kind="note",
        title="test",
        text="body",
        media_paths=[str(image)],
    )

    first = await tool.publish(request, event_id="social-event")
    assert first.executed is False
    assert first.decision.effect == "require_approval"
    assert first.result is not None
    assert provider.calls == []

    approval_id = first.result["approval_id"]
    assert await store.decide(approval_id, "approved") is True
    second = await tool.publish(request, event_id="social-event", approval=approval_id)

    assert second.executed is True
    assert provider.calls[0][1] == "social-event"
    assert provider.calls[0][0].text.startswith("[AI]\n\nbody")
    assert second.result["status"] == "published"


@pytest.mark.asyncio
async def test_social_publish_api_returns_approval_or_receipt():
    class FakeTool:
        async def publish(self, request, **kwargs):
            return ToolExecution(
                executed=True,
                decision=PolicyDecision(effect="allow", reason="approved"),
                result={"status": "published", "verified": True},
            )

    app = create_app(
        FakeEventService(),
        IdempotentProcessor(),
        lambda event_id: None,
        None,
        force_shadow=False,
        social_publish_tool=FakeTool(),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/v1/social/publish",
            headers={"Idempotency-Key": "social-api-event"},
            json={
                "platform": "xiaohongshu",
                "account": "creator",
                "kind": "note",
                "title": "test",
                "text": "body",
                "media_paths": [],
            },
        )
    assert response.status_code == 200
    assert response.json()["event_id"] == "social-api-event"
    assert response.json()["result"]["status"] == "published"


def test_social_media_must_be_under_configured_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"x")
    request = SocialPublishRequest(
        platform="douyin",
        account="creator",
        kind="note",
        title="test",
        text="body",
        media_paths=[str(outside)],
    )
    with pytest.raises(ValueError, match="configured social media root"):
        build_publish_spec(request, media_root=root, identity_label="[AI]")