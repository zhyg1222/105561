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
