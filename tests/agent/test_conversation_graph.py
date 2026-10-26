import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from xiaojuju_agent.graph.conversation import build_conversation_graph
from xiaojuju_agent.identity import IdentityBundle

IDENTITY = IdentityBundle(content="private identity", sha256="a" * 64)


class EchoModel:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append([(message.type, message.content) for message in messages])
        return AIMessage(content="echo: " + messages[-1].content)


@pytest.mark.asyncio
async def test_graph_checkpoints_thread():
    model = EchoModel()
    graph = build_conversation_graph(model, InMemorySaver(), IDENTITY)
    config = {"configurable": {"thread_id": "owner"}}
    await graph.ainvoke({"user_text": "first", "messages": []}, config)
    second = await graph.ainvoke({"user_text": "second", "messages": []}, config)

    assert model.calls[1] == [
        ("system", "private identity"),
        ("human", "first"),
        ("ai", "echo: first"),
        ("human", "second"),
    ]
    assert second["reply"] == "echo: second"
    assert not [message for message in second["messages"] if message.type == "system"]


@pytest.mark.asyncio
async def test_postgres_checkpoint_roundtrip(postgres_saver):
    model = EchoModel()
    graph = build_conversation_graph(model, postgres_saver, IDENTITY)
    config = {"configurable": {"thread_id": "owner-pg"}}
    await graph.ainvoke({"user_text": "persisted"}, config)
    snapshot = await graph.aget_state(config)
    assert snapshot.values["reply"] == "echo: persisted"

    recreated_model = EchoModel()
    recreated_graph = build_conversation_graph(recreated_model, postgres_saver, IDENTITY)
    await recreated_graph.ainvoke({"user_text": "second"}, config)
    assert recreated_model.calls[0][1] == ("human", "persisted")
