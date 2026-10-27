import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from langchain_core.tools import StructuredTool

from .context import current_event_id, current_event_shadow
from .contracts import PolicyInput
from .policy import PolicyClient, PolicyDecision


@dataclass(frozen=True)
class ToolExecution:
    executed: bool
    decision: PolicyDecision
    result: Any = None


class ToolExecutor:
    def __init__(self, policy_client: PolicyClient | None, approval_store=None):
        self.policy_client = policy_client
        self.approval_store = approval_store

    async def execute(
        self,
        call: PolicyInput,
        handler: Callable[[], Any],
        *,
        approval: str | None = None,
    ) -> ToolExecution:
        if call.shadow and call.side_effect:
            return ToolExecution(
                executed=False,
                decision=PolicyDecision(effect="deny", reason="shadow_side_effect"),
            )
        if self.policy_client is None:
            return ToolExecution(
                executed=False,
                decision=PolicyDecision(effect="deny", reason="policy_unavailable"),
            )

        decision = await self.policy_client.decision(call)
        if decision.effect == "require_approval":
            if not approval or self.approval_store is None:
                pending = None
                if self.approval_store is not None:
                    pending = await self.approval_store.create(
                        event_id=call.event_id,
                        tool=call.tool,
                        args=call.args,
                    )
                return ToolExecution(
                    executed=False,
                    decision=PolicyDecision(effect="require_approval", reason="approval_required"),
                    result={"approval_id": pending["approval_id"], "status": "pending"}
                    if pending
                    else None,
                )
            approved = await self.approval_store.consume(
                approval,
                event_id=call.event_id,
                tool=call.tool,
                args=call.args,
            )
            if not approved:
                return ToolExecution(
                    executed=False,
                    decision=PolicyDecision(effect="require_approval", reason="approval_invalid"),
                )
            decision = PolicyDecision(effect="allow", reason="approval_consumed")
        if decision.effect != "allow":
            return ToolExecution(executed=False, decision=decision)

        value = handler()
        if inspect.isawaitable(value):
            value = await value
        return ToolExecution(executed=True, decision=decision, result=value)


class MessageSendTool:
    """Policy-gated bridge from an Agent reply to the Postgres outbox."""

    def __init__(self, executor: ToolExecutor, outbox):
        self.executor = executor
        self.outbox = outbox

    async def send(
        self,
        *,
        source: str,
        contact_id: str,
        text: str,
        event_id: str,
        shadow: bool | None = None,
        approval: str | None = None,
        kind: str = "message",
    ) -> ToolExecution:
        if shadow is None:
            shadow = current_event_shadow()
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="message.send",
            args={"text": text},
            contact_id=contact_id,
            event_id=event_id,
            risk="normal",
            shadow=shadow,
            side_effect=True,
        )
        message_id = f"{event_id}:send"
        return await self.executor.execute(
            call,
            lambda: self.outbox.enqueue(
                contact_id,
                text,
                kind=kind,
                message_id=message_id,
            ),
            approval=approval,
        )


def as_langchain_message_tool(tool: MessageSendTool) -> StructuredTool:
    async def _send(text: str, contact_id: str = "owner") -> str:
        event_id = current_event_id()
        if not event_id:
            return json.dumps({"sent": False, "reason": "missing_event_context"}, ensure_ascii=False)
        execution = await tool.send(
            source="wechat",
            contact_id=contact_id,
            text=text,
            event_id=event_id,
            shadow=current_event_shadow(),
        )
        return json.dumps(
            {
                "executed": execution.executed,
                "decision": execution.decision.model_dump(),
                "result": execution.result,
            },
            ensure_ascii=False,
        )

    return StructuredTool.from_function(
        name="message_send",
        description="Send a text message to the owner through the real WeChat outbox. Owner only.",
        coroutine=_send,
    )
