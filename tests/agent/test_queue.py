import pytest

from xiaojuju_agent.queue_app import MAX_RETRIES, handle_task_failure


def test_celery_task_is_registered():
    from xiaojuju_agent.queue_app import celery_app

    assert "xiaojuju.process_event" in celery_app.tasks


@pytest.mark.asyncio
async def test_retry_and_final_failure_are_persisted():
    class Store:
        def __init__(self):
            self.calls = []

        async def mark_retry(self, event_id, error):
            self.calls.append(("retry", event_id, error))

        async def mark_failed(self, event_id, error):
            self.calls.append(("failed", event_id, error))

    store = Store()
    await handle_task_failure(store, "event-1", "boom", retries=0, max_retries=MAX_RETRIES)
    await handle_task_failure(
        store,
        "event-1",
        "boom",
        retries=MAX_RETRIES,
        max_retries=MAX_RETRIES,
    )

    assert [call[0] for call in store.calls] == ["retry", "failed"]
