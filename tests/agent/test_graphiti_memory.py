from datetime import UTC, datetime

import pytest
from pydantic import SecretStr

from xiaojuju_agent.graphiti_memory import GraphitiMemoryProvider, HashEmbedder
from xiaojuju_agent.settings import Settings
from xiaojuju_core.contacts import contact_key


class FakeLegacy:
    def __init__(self):
        self.recalls = []
        self.writes = []

    async def recall(self, contact, query, limit=4):
        self.recalls.append((contact, query))
        return [{"user": "legacy fact", "assistant": ""}]

    async def remember(self, contact, user_text, assistant_text, *, event_id, source):
        self.writes.append((contact, user_text, assistant_text, event_id, source))
        return {"event_id": event_id}


class FakeGraph:
    def __init__(self):
        self.searches = []
        self.episodes = []
        self.closed = False

    async def search(self, query, *, group_ids, num_results):
        self.searches.append((query, group_ids, num_results))
        return [SimpleEdge("graphiti fact")]

    async def add_episode(self, **kwargs):
        self.episodes.append(kwargs)

    async def close(self):
        self.closed = True


class SimpleEdge:
    def __init__(self, fact):
        self.fact = fact
        self.valid_at = datetime.now(UTC)
        self.invalid_at = None


@pytest.mark.asyncio
async def test_hash_embedder_is_deterministic_and_normalized():
    embedder = HashEmbedder(32)
    first = await embedder.create("老大喜欢直接回答")
    second = await embedder.create("老大喜欢直接回答")
    assert first == second
    assert len(first) == 32
    assert abs(sum(item * item for item in first) - 1.0) < 1e-6


@pytest.mark.asyncio
async def test_graphiti_provider_writes_and_recalls_with_contact_isolation():
    settings = Settings(
        graphiti_enabled=True,
        deepseek_api_key=SecretStr("dummy"),
        neo4j_password=SecretStr("dummy"),
    )
    legacy = FakeLegacy()
    graph = FakeGraph()
    provider = GraphitiMemoryProvider(settings, legacy=legacy, client_factory=lambda _: graph)

    rows = await provider.recall("老大", "喜欢什么表达")
    assert rows[0]["fact"] == "graphiti fact"
    assert graph.searches[0][1] == ["contact_" + contact_key("老大")]

    result = await provider.remember(
        "老大",
        "我喜欢直接",
        "记住了",
        event_id="event-graphiti",
        source="wechat",
    )
    assert result["event_id"] == "event-graphiti"
    assert legacy.writes[0][0] == "老大"
    await provider.drain()
    assert graph.episodes[0]["group_id"].startswith("contact_")
    assert "我喜欢直接" in graph.episodes[0]["episode_body"]


@pytest.mark.asyncio
async def test_durable_candidate_uses_stable_episode_business_key():
    settings = Settings(
        graphiti_enabled=True,
        deepseek_api_key=SecretStr("dummy"),
        neo4j_password=SecretStr("dummy"),
    )
    legacy = FakeLegacy()
    graph = FakeGraph()
    provider = GraphitiMemoryProvider(settings, legacy=legacy, client_factory=lambda _: graph)
    candidate = {
        "event_id": "event-durable",
        "contact_id": "owner",
        "user_text": "hello",
        "assistant_text": "world",
        "source": "wechat",
        "group_id": "contact_owner",
        "reference_time": datetime.now(UTC),
    }

    await provider.persist_candidate(candidate)

    assert graph.episodes[0]["name"] == "conversation:event-durable"
    assert "uuid" not in graph.episodes[0]
    assert legacy.writes[0][3] == "event-durable"


@pytest.mark.asyncio
async def test_graphiti_failure_falls_back_to_legacy():
    settings = Settings(
        graphiti_enabled=True,
        deepseek_api_key=SecretStr("dummy"),
        neo4j_password=SecretStr("dummy"),
    )
    legacy = FakeLegacy()

    def broken_factory(_):
        raise RuntimeError("neo4j unavailable")

    provider = GraphitiMemoryProvider(settings, legacy=legacy, client_factory=broken_factory)
    rows = await provider.recall("老大", "query")
    assert rows[0]["user"] == "legacy fact"
    result = await provider.remember(
        "老大", "user", "assistant", event_id="event-fallback", source="wechat"
    )
    assert result["event_id"] == "event-fallback"
