from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class ConversationState(TypedDict, total=False):
    user_text: str
    messages: Annotated[list[AnyMessage], add_messages]
    reply: str
    trace_id: str
    identity_hash: str
