from xiaojuju_agent.events import SubmitResult


class FakeEventService:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.events = {}
        self.published = []

    async def accept(self, event):
        if self.fail:
            raise ConnectionError("postgres down")
        existing = self.events.get(event.event_id)
        if existing is not None:
            return SubmitResult(False, existing["status"], existing["shadow"], existing["event_id"])
        stored = event.model_dump()
        stored["status"] = "received"
        self.events[event.event_id] = stored
        return SubmitResult(True, "received", event.shadow, event.event_id)

    async def submit(self, event, dispatch):
        result = await self.accept(event)
        if result.accepted and not result.shadow:
            dispatch(result.event_id)
            self.published.append(result.event_id)
        return result

    async def publish_pending(self, dispatch, limit=100):
        return 0


class IdempotentProcessor:
    def __init__(self):
        self.results = {}
        self.model_calls = 0
        self.process_calls = 0
        self.calls = []

    async def __call__(self, event_id):
        self.process_calls += 1
        self.calls.append(event_id)
        if event_id in self.results:
            return self.results[event_id]
        self.model_calls += 1
        result = {"event_id": event_id, "reply": f"reply-{self.model_calls}", "trace_id": event_id}
        self.results[event_id] = result
        return result
