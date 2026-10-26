import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from xiaojuju_agent.graph.conversation import build_conversation_graph


class EchoModel:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append([message.content for message in messages])
        return AIMessage(content="收到：" + messages[-1].content)


@pytest.mark.asyncio
async def test_graph_checkpoints_thread():
    model = EchoModel()
    graph = build_conversation_graph(model, InMemorySaver())
    config = {"configurable": {"thread_id": "owner"}}
    await graph.ainvoke({"user_text": "第一句"}, config)
    second = await graph.ainvoke({"user_text": "第二句"}, config)
    assert model.calls[1] == ["第一句", "收到：第一句", "第二句"]
    assert second["messages"][-4].content == "第一句"
    assert second["reply"] == "收到：第二句"


@pytest.mark.asyncio
async def test_postgres_checkpoint_roundtrip(postgres_saver):
    model = EchoModel()
    graph = build_conversation_graph(model, postgres_saver)
    config = {"configurable": {"thread_id": "owner-pg"}}
    await graph.ainvoke({"user_text": "\u6301\u4e45\u5316"}, config)
    snapshot = await graph.aget_state(config)
    assert snapshot.values["reply"] == "\u6536\u5230\uff1a\u6301\u4e45\u5316"

    recreated_model = EchoModel()
    recreated_graph = build_conversation_graph(recreated_model, postgres_saver)
    await recreated_graph.ainvoke({"user_text": "\u7b2c\u4e8c\u53e5"}, config)
    assert recreated_model.calls[0][0] == "\u6301\u4e45\u5316"
