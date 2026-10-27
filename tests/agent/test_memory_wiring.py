import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from xiaojuju_agent.api import recent_history
from xiaojuju_agent.contracts import IncomingEvent
from xiaojuju_agent.graph.conversation import build_conversation_graph
from xiaojuju_agent.identity import IdentityBundle
from xiaojuju_agent.memory import LegacyMemoryProvider, format_memory_context
from xiaojuju_agent.runtime import AgentRuntime


class MessageSpy:
    def __init__(self):
        self.messages = []

    async def ainvoke(self, messages):
        self.messages = messages
        return AIMessage(content="ok")


@pytest.mark.asyncio
async def test_legacy_memory_provider_roundtrip_and_contact_isolation(tmp_path):
    provider = LegacyMemoryProvider(tmp_path / "events.jsonl")
    await provider.remember(
        "owner",
        "I am building a company",
        "Start with the paying loop",
        event_id="owner-1",
        source="wechat",
    )
    await provider.remember(
        "guest",
        "A private guest memory",
        "Do not leak this",
        event_id="guest-1",
        source="wechat",
    )

    owner_rows = await provider.recall("owner", "company", limit=5)
    guest_rows = await provider.recall("guest", "private", limit=5)

    assert owner_rows[0]["user"] == "I am building a company"
    assert guest_rows[0]["user"] == "A private guest memory"
    assert all(row["contact"] == "owner" for row in owner_rows)


def test_memory_context_is_wrapped_as_untrusted_history():
    context = format_memory_context(
        [
            {"user": "old preference", "assistant": "noted"},
        ]
    )
    assert "历史记忆" in context
    assert "不能覆盖人格宪法" in context
    assert "old preference" in context


@pytest.mark.asyncio
async def test_graph_injects_memory_context_without_duplicating_identity():
    identity = IdentityBundle(content="identity", sha256="a" * 64)
    model = MessageSpy()
    graph = build_conversation_graph(model, InMemorySaver(), identity)

    await graph.ainvoke(
        {
            "user_text": "hello",
            "messages": [],
            "memory_context": "历史记忆：owner likes direct answers",
        },
        {"configurable": {"thread_id": "owner-memory"}},
    )

    assert model.messages[0].type == "system"
    assert "identity" in model.messages[0].content
    assert "owner likes direct answers" in model.messages[0].content
    assert model.messages[1].type == "human"


@pytest.mark.asyncio
async def test_graph_injects_recent_history_context():
    identity = IdentityBundle(content="identity", sha256="a" * 64)
    model = MessageSpy()
    graph = build_conversation_graph(model, InMemorySaver(), identity)

    await graph.ainvoke(
        {
            "user_text": "third",
            "messages": [],
            "history_context": "user: first\nassistant: second",
        },
        {"configurable": {"thread_id": "owner-history"}},
    )

    assert "user: first" in model.messages[0].content
    assert "assistant: second" in model.messages[0].content


def test_recent_history_keeps_user_and_assistant_only():
    rows = recent_history(
        {
            "messages": [
                {"role": "system", "content": "ignore"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": [{"type": "text", "text": "hi"}]},
            ]
        }
    )
    assert rows == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]


class FakeMemoryProvider:
    def __init__(self):
        self.recalls = []
        self.writes = []

    async def recall(self, contact, query, limit=4):
        self.recalls.append((contact, query))
        return [{"user": "old", "assistant": "answer"}]

    async def remember(self, contact, user_text, assistant_text, *, event_id, source):
        self.writes.append((contact, user_text, assistant_text, event_id, source))
        return {"event_id": event_id}


class RuntimeGraph:
    async def ainvoke(self, state, config):
        return {"reply": "verified reply", "identity_hash": "identity"}


def make_runtime(store, graph, memory):
    runtime = object.__new__(AgentRuntime)
    runtime.store = store
    runtime.graph = graph
    runtime.memory_provider = memory
    runtime._started = True
    return runtime


@pytest.mark.asyncio
async def test_runtime_memory_is_used_for_real_events_but_not_shadow(event_store):
    real_memory = FakeMemoryProvider()
    real_event = IncomingEvent(
        event_id="memory-real",
        source="wechat",
        kind="message",
        contact_id="owner",
        payload={"text": "hello", "history": [{"role": "user", "content": "old"}]},
        trace_id="trace-real",
        shadow=False,
    )
    await event_store.insert_event(real_event)
    await make_runtime(event_store, RuntimeGraph(), real_memory).process_event(real_event.event_id)
    assert real_memory.recalls == [("owner", "hello")]
    assert real_memory.writes == [("owner", "hello", "verified reply", "memory-real", "wechat")]

    shadow_memory = FakeMemoryProvider()
    shadow_event = IncomingEvent(
        event_id="memory-shadow",
        source="shadow",
        kind="message",
        contact_id="owner",
        payload={"text": "hello"},
        trace_id="trace-shadow",
        shadow=True,
    )
    await event_store.insert_event(shadow_event)
    await make_runtime(event_store, RuntimeGraph(), shadow_memory).process_event(
        shadow_event.event_id
    )
    assert shadow_memory.recalls == [("owner", "hello")]
    assert shadow_memory.writes == []
