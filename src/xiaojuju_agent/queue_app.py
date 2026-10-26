import asyncio
import sys

from celery import Celery

from .runtime import AgentRuntime
from .settings import Settings

settings = Settings.from_env()
celery_app = Celery("xiaojuju", broker=settings.valkey_url, backend=settings.valkey_url)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delay=10,
)


async def _run(event_id: str):
    runtime = AgentRuntime(settings)
    await runtime.start()
    try:
        return await runtime.process_event(event_id)
    finally:
        await runtime.stop()


@celery_app.task(name="xiaojuju.process_event", bind=True, max_retries=5)
def process_event(self, event_id: str):
    try:
        result = asyncio.run(_run(event_id))
    except Exception as exc:  # noqa: BLE001 - Celery must retry any operational failure
        raise self.retry(exc=exc, countdown=min(60, 2**self.request.retries))
    return {"event_id": event_id, "status": "completed", "result": result}


if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
