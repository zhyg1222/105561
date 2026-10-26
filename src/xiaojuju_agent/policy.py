from typing import Literal

import httpx
from pydantic import BaseModel, ValidationError

from .contracts import PolicyInput


class PolicyDecision(BaseModel):
    effect: Literal["allow", "deny", "require_approval"]
    reason: str


class PolicyClient:
    def __init__(self, base_url: str, transport: httpx.AsyncBaseTransport | None = None):
        self.base_url = base_url.rstrip("/")
        self.transport = transport

    async def decision(self, payload: PolicyInput) -> PolicyDecision:
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=3.0) as client:
                response = await client.post(
                    self.base_url + "/v1/data/xiaojuju/authz/decision",
                    json={"input": payload.model_dump()},
                )
                response.raise_for_status()
                raw = response.json().get("result")
                if not raw:
                    raise ValueError("empty policy decision")
                return PolicyDecision.model_validate(raw)
        except (httpx.HTTPError, KeyError, TypeError, ValueError, ValidationError):
            return PolicyDecision(effect="deny", reason="policy_unavailable")
