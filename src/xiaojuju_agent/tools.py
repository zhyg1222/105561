import inspect
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .contracts import PolicyInput
from .policy import PolicyClient, PolicyDecision


@dataclass(frozen=True)
class ToolExecution:
    executed: bool
    decision: PolicyDecision
    result: Any = None


class ToolExecutor:
    def __init__(self, policy_client: PolicyClient | None):
        self.policy_client = policy_client

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
            decision = PolicyDecision(
                effect="require_approval",
                reason="approval_required" if not approval else "approval_not_verified",
            )
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
        shadow: bool = False,
        approval: str | None = None,
        kind: str = "message",
    ) -> ToolExecution:
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="message.send",
            args={"text": text},
            contact_id=contact_id,
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
