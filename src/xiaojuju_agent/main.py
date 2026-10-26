from contextlib import asynccontextmanager

from .api import create_app
from .events import EventService
from .observability import configure_observability
from .policy import PolicyClient
from .queue_app import process_event
from .runtime import AgentRuntime
from .settings import Settings


class RuntimeEventService:
    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime

    async def submit(self, event, dispatch):
        return await EventService(self.runtime.store).submit(event, dispatch)


class RuntimeGraph:
    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime

    async def ainvoke(self, state: dict, config: dict) -> dict:
        thread_id = config["configurable"]["thread_id"]
        return await self.runtime.reply(state, thread_id)


def create_production_app():
    settings = Settings.from_env()
    runtime = AgentRuntime(settings)
    policy = PolicyClient(settings.opa_url)

    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = runtime
        await runtime.start()
        try:
            yield
        finally:
            await runtime.stop()

    app = create_app(
        event_service=RuntimeEventService(runtime),
        graph=RuntimeGraph(runtime),
        dispatch=lambda event_id: process_event.delay(event_id),
        policy_client=policy,
    )
    app.router.lifespan_context = lifespan
    configure_observability(settings, app=app)
    return app


app = create_production_app()
