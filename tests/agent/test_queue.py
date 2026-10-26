import pytest

from xiaojuju_agent.runtime import AgentRuntime


def test_celery_task_is_registered():
    from xiaojuju_agent.queue_app import celery_app

    assert "xiaojuju.process_event" in celery_app.tasks


@pytest.mark.asyncio
async def test_process_event_returns_saved_result_without_model_call():
    class SavedStore:
        async def get_event(self, event_id):
            return {"result": {"reply": "saved"}}

    runtime = object.__new__(AgentRuntime)
    runtime.store = SavedStore()
    assert await runtime.process_event("event-1") == {"reply": "saved"}
