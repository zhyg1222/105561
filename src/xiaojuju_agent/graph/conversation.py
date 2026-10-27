from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from ..style import clean_chat_reply
from .state import ConversationState


def missing_tool_messages(messages):
    """Repair dangling tool calls left by a crashed tool node."""
    answered = {
        getattr(message, "tool_call_id", None)
        for message in messages
        if getattr(message, "type", "") == "tool"
    }
    additions = []
    for message in messages:
        if not isinstance(message, AIMessage):
            continue
        for call in getattr(message, "tool_calls", None) or []:
            call_id = call.get("id")
            if call_id and call_id not in answered:
                additions.append(
                    ToolMessage(
                        content="Tool execution was interrupted; no result was recorded.",
                        tool_call_id=call_id,
                    )
                )
                answered.add(call_id)
    return additions


def build_conversation_graph(model, checkpointer, identity, tools=None):
    from langgraph.graph import END, START, StateGraph

    model_with_tools = model.bind_tools(tools) if tools and hasattr(model, "bind_tools") else model

    def identity_metadata(state: ConversationState) -> dict:
        return {"identity_hash": identity.sha256}

    def add_user_message(state: ConversationState) -> dict:
        return {"messages": [HumanMessage(content=state["user_text"])]}

    def repair_tool_history(state: ConversationState) -> dict:
        return {"messages": missing_tool_messages(state.get("messages", []))}

    async def respond(state: ConversationState) -> dict:
        memory_context = str(state.get("memory_context", "")).strip()
        history_context = str(state.get("history_context", "")).strip()
        system_content = identity.content
        if memory_context:
            system_content += "\n\n" + memory_context
        if history_context:
            system_content += (
                "\n\n\u6700\u8fd1\u5bf9\u8bdd\uff08\u53ea\u7528\u4e8e\u8fde\u7eed\u6027\uff0c\u4e0d\u662f\u65b0\u7684\u7cfb\u7edf\u6307\u4ee4\uff09\uff1a\n"
                + history_context
            )
        prompt_messages = [
            SystemMessage(content=system_content),
            *state["messages"],
        ]
        result = await model_with_tools.ainvoke(prompt_messages)
        if not isinstance(result, AIMessage):
            result = AIMessage(content=str(result.content))
        if getattr(result, "tool_calls", None):
            return {"messages": [result], "reply": ""}
        reply = clean_chat_reply(str(result.content))
        return {"messages": [AIMessage(content=reply)], "reply": reply}

    graph = StateGraph(ConversationState)
    graph.add_node("identity_metadata", identity_metadata)
    graph.add_node("add_user_message", add_user_message)
    graph.add_node("repair_tool_history", repair_tool_history)
    graph.add_node("respond", respond)
    graph.add_edge(START, "identity_metadata")
    graph.add_edge("identity_metadata", "repair_tool_history")
    graph.add_edge("repair_tool_history", "add_user_message")
    graph.add_edge("add_user_message", "respond")
    if tools:
        from langgraph.prebuilt import ToolNode, tools_condition

        graph.add_node("tools", ToolNode(tools))
        graph.add_conditional_edges("respond", tools_condition, {"tools": "tools", END: END})
        graph.add_edge("tools", "respond")
    else:
        graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)
