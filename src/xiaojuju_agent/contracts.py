from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IncomingEvent(BaseModel):
    event_id: str = Field(min_length=1)
    source: Literal["wechat", "live", "autonomy", "phone", "browser", "shadow"]
    kind: Literal["message", "notification", "tick", "tool_result"]
    contact_id: str | None = None
    external_id: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any]
    trace_id: str = Field(min_length=1)
    shadow: bool = True


class ReplyResult(BaseModel):
    event_id: str
    reply: str
    should_respond: bool = True
    trace_id: str


class PolicyInput(BaseModel):
    actor: str
    source: str
    tool: str
    args: dict[str, Any]
    contact_id: str | None = None
    risk: str = "normal"
    shadow: bool = True
