from contextvars import ContextVar

CURRENT_EVENT_ID: ContextVar[str | None] = ContextVar("xiaojuju_event_id", default=None)


def set_current_event_id(event_id: str | None):
    return CURRENT_EVENT_ID.set(str(event_id) if event_id else None)


def reset_current_event_id(token) -> None:
    CURRENT_EVENT_ID.reset(token)


def current_event_id() -> str | None:
    return CURRENT_EVENT_ID.get()
