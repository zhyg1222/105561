from langchain_core.messages import AIMessage, HumanMessage

from .state import ConversationState


def identity_messages(state: ConversationState) -> dict:
    return {"messages": [HumanMessage(content=state["user_text"])]}


def build_conversation_graph(model, checkpointer):
    from langgraph.graph import END, START, StateGraph

    async def respond(state: ConversationState) -> dict:
        result = await model.ainvoke(state["messages"])
        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content))
        return {"messages": [result], "reply": result.content}

    graph = StateGraph(ConversationState)
    graph.add_node("identity_messages", identity_messages)
    graph.add_node("respond", respond)
    graph.add_edge(START, "identity_messages")
    graph.add_edge("identity_messages", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)
