from pathlib import Path
from .brain import respond_event
from .event_bus import EventBus
from .paths import Paths

PATHS = Paths.production()


def _topic_and_priority(event: dict) -> tuple[str, int]:
    source = str(event.get("source") or "")
    if source == "wechat":
        return "wechat.message", 100
    if source == "live":
        return "live.message", 80
    return "user", 100


def process_event(
    event: dict,
    responder=respond_event,
    *,
    bus_path: Path | str | None = None,
    stale_after: float = 600,
) -> dict:
    """Process an inbound model event exactly once, with persistent retry.

    A duplicate completed event returns the stored reply. A duplicate event
    whose previous attempt crashed can be reclaimed after the stale timeout.
    """
    event_id = str(event.get("event_id") or "").strip()
    text = str(event.get("text") or "").strip()
    if not event_id or not text:
        raise ValueError("event_id and text are required")
    topic, priority = _topic_and_priority(event)
    path = Path(bus_path) if bus_path else PATHS.event_bus
    with EventBus(path) as bus:
        bus.enqueue(event_id, topic, event, priority=priority)
        bus.requeue_stale(stale_after)
        existing = bus.get(event_id)
        if existing and existing.get("status") == "completed":
            saved = existing.get("result")
            if isinstance(saved, dict):
                return saved
            return {
                "event_id": event_id,
                "reply": "",
                "should_respond": False,
                "decision": {"move": "\u8df3\u8fc7", "emotion": "\u677e\u5f1b", "intent": "\u4e8b\u4ef6\u5df2\u5b8c\u6210", "needs_web": False},
                "sources": [],
            }
        claimed = bus.claim(event_id)
        if claimed is None:
            current = bus.get(event_id) or {}
            raise RuntimeError(f"event is not claimable: {current.get('status', 'missing')}")
        try:
            result = responder(event)
        except Exception as exc:
            bus.fail(event_id, repr(exc), retry=True)
            raise
        if not isinstance(result, dict):
            result = {"reply": str(result or ""), "should_respond": True}
        bus.complete(event_id, result)
        return result
