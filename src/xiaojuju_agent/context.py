from contextvars import ContextVar

CURRENT_EVENT_ID: ContextVar[str | None] = ContextVar("xiaojuju_event_id", default=None)
CURRENT_EVENT_SHADOW: ContextVar[bool] = ContextVar("xiaojuju_event_shadow", default=False)


def set_current_event_id(event_id: str | None):
    return CURRENT_EVENT_ID.set(str(event_id) if event_id else None)


def reset_current_event_id(token) -> None:
    CURRENT_EVENT_ID.reset(token)


def set_current_event_shadow(shadow: bool):
    return CURRENT_EVENT_SHADOW.set(bool(shadow))


def reset_current_event_shadow(token) -> None:
    CURRENT_EVENT_SHADOW.reset(token)


def current_event_id() -> str | None:
    return CURRENT_EVENT_ID.get()


def current_event_shadow() -> bool:
    return bool(CURRENT_EVENT_SHADOW.get())
