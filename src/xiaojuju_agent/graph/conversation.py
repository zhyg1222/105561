from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from .state import ConversationState


def build_conversation_graph(model, checkpointer, identity):
    from langgraph.graph import END, START, StateGraph

    def identity_metadata(state: ConversationState) -> dict:
        return {"identity_hash": identity.sha256}

    def add_user_message(state: ConversationState) -> dict:
        return {"messages": [HumanMessage(content=state["user_text"])]}

    async def respond(state: ConversationState) -> dict:
        prompt_messages = [
            SystemMessage(content=identity.content),
            *state["messages"],
        ]
        result = await model.ainvoke(prompt_messages)
        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content))
        return {"messages": [result], "reply": result.content}

    graph = StateGraph(ConversationState)
    graph.add_node("identity_metadata", identity_metadata)
    graph.add_node("add_user_message", add_user_message)
    graph.add_node("respond", respond)
    graph.add_edge(START, "identity_metadata")
    graph.add_edge("identity_metadata", "add_user_message")
    graph.add_edge("add_user_message", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)
