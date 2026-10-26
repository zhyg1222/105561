import asyncio
import logging
import sys

from celery import Celery
from opentelemetry import trace
from opentelemetry.instrumentation.celery import CeleryInstrumentor

from .db import Database
from .events import EventProcessing, EventStore
from .observability import configure_observability
from .runtime import AgentRuntime
from .settings import Settings

MAX_RETRIES = 8
logger = logging.getLogger(__name__)

settings = Settings.from_env()
configure_observability(settings)
celery_app = Celery("xiaojuju", broker=settings.valkey_url, backend=settings.valkey_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
)
CeleryInstrumentor().instrument()


async def _run(event_id: str):
    runtime = AgentRuntime(settings)
    await runtime.start()
    try:
        return await runtime.process_event(event_id)
    finally:
        await runtime.stop()


async def _record_failure(event_id: str, error: str, *, retry: bool) -> None:
    db = Database(settings)
    await db.open()
    try:
        store = EventStore(db)
        if retry:
            await store.mark_retry(event_id, error)
        else:
            await store.mark_failed(event_id, error)
    finally:
        await db.close()


async def _mark_failed(event_id: str, error: str) -> None:
    await _record_failure(event_id, error, retry=False)


async def _mark_retry(event_id: str, error: str) -> None:
    await _record_failure(event_id, error, retry=True)


async def handle_task_failure(
    store, event_id: str, error: str, *, retries: int, max_retries: int
) -> None:
    if retries < max_retries:
        await store.mark_retry(event_id, error)
    else:
        await store.mark_failed(event_id, error)


@celery_app.task(name="xiaojuju.process_event", bind=True, max_retries=MAX_RETRIES)
def process_event(self, event_id: str):
    tracer = trace.get_tracer("xiaojuju.worker")
    try:
        with tracer.start_as_current_span("event.process") as span:
            span.set_attribute("event_id", event_id)
            result = asyncio.run(_run(event_id))
    except EventProcessing as exc:
        if self.request.retries >= MAX_RETRIES:
            raise
        raise self.retry(exc=exc, countdown=min(30, 2**self.request.retries))
    except Exception as exc:
        final = self.request.retries >= MAX_RETRIES
        try:
            if final:
                asyncio.run(_mark_failed(event_id, repr(exc)))
            else:
                asyncio.run(_mark_retry(event_id, repr(exc)))
        except Exception:
            logger.exception("failed to persist event failure state")
        if final:
            raise
        raise self.retry(exc=exc, countdown=min(60, 2**self.request.retries))

    return {"event_id": event_id, "status": "completed", "result": result}


if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
