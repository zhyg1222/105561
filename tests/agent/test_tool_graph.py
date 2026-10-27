import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver

from xiaojuju_agent.graph.conversation import build_conversation_graph, missing_tool_messages
from xiaojuju_agent.identity import IdentityBundle


class ToolModel:
    def __init__(self):
        self.calls = 0
        self.tools = []

    def bind_tools(self, tools):
        self.tools = tools
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        if self.calls == 1:
            return AIMessage(
                content="",
                tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call-1"}],
            )
        return AIMessage(content="answer after tool")


@pytest.mark.asyncio
async def test_langgraph_executes_policy_wrapped_web_search_tool():
    model = ToolModel()
    search = StructuredTool.from_function(
        func=lambda query: "public result",
        name="web_search",
        description="read only search",
    )
    identity = IdentityBundle(content="identity", sha256="a" * 64)
    graph = build_conversation_graph(model, InMemorySaver(), identity, tools=[search])

    result = await graph.ainvoke(
        {"user_text": "find something", "messages": []},
        {"configurable": {"thread_id": "tool-thread"}},
    )

    assert model.calls == 2
    assert result["reply"] == "answer after tool"


def test_dangling_tool_call_is_repaired_with_a_tool_message():
    message = AIMessage(
        content="",
        tool_calls=[{"name": "web_search", "args": {"query": "x"}, "id": "dangling"}],
    )
    repaired = missing_tool_messages([message])
    assert len(repaired) == 1
    assert repaired[0].tool_call_id == "dangling"
    assert "interrupted" in repaired[0].content
