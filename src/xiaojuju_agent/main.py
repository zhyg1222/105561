import asyncio
import logging
from contextlib import asynccontextmanager

from .api import create_app
from .events import EventService
from .memory import LegacyMemoryProvider
from .observability import configure_observability
from .policy import PolicyClient
from .queue_app import process_event
from .runtime import AgentRuntime
from .settings import Settings
from .tools import ToolExecutor
from .web import WebFetchTool, WebSearchTool, as_langchain_tools

logger = logging.getLogger(__name__)
PUBLISH_INTERVAL_SECONDS = 2.0


class RuntimeEventService:
    def __init__(self, runtime: AgentRuntime):
        self.runtime = runtime

    async def _service(self) -> EventService:
        await self.runtime.ensure_started()
        return EventService(self.runtime.store)

    async def accept(self, event):
        return await (await self._service()).accept(event)

    async def submit(self, event, dispatch):
        return await (await self._service()).submit(event, dispatch)

    async def publish_pending(self, dispatch, limit: int = 100):
        return await (await self._service()).publish_pending(dispatch, limit=limit)


def create_production_app(
    settings: Settings | None = None,
    runtime: AgentRuntime | None = None,
    policy_client: PolicyClient | None = None,
):
    settings = settings or Settings.from_env()
    policy = policy_client or PolicyClient(settings.opa_url)
    tool_executor = ToolExecutor(policy)
    web_search = WebSearchTool(tool_executor)
    web_fetch = WebFetchTool(tool_executor)
    runtime = runtime or AgentRuntime(
        settings,
        memory_provider=LegacyMemoryProvider(),
        tools=as_langchain_tools(web_search, web_fetch),
    )
    event_service = RuntimeEventService(runtime)

    def dispatch(event_id: str) -> None:
        process_event.delay(event_id)

    async def publish_forever():
        while True:
            try:
                await event_service.publish_pending(dispatch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - publisher must survive outages
                logger.warning("event publisher is waiting: %s", exc)
            await asyncio.sleep(PUBLISH_INTERVAL_SECONDS)

    @asynccontextmanager
    async def lifespan(app):
        app.state.runtime = runtime
        app.state.startup_error = None
        try:
            await runtime.start()
        except Exception as exc:
            app.state.startup_error = exc
            logger.exception("agent runtime startup failed")

        publisher = asyncio.create_task(publish_forever())
        try:
            yield
        finally:
            publisher.cancel()
            try:
                await publisher
            except asyncio.CancelledError:
                pass
            try:
                await runtime.stop()
            except Exception:
                logger.exception("agent runtime shutdown failed")

    app = create_app(
        event_service=event_service,
        process_event=lambda event_id: runtime.process_event(event_id),
        dispatch=dispatch,
        policy_client=policy,
        force_shadow=settings.shadow_mode,
        tool_executor=tool_executor,
    )
    app.router.lifespan_context = lifespan
    configure_observability(settings, app=app)
    return app


app = create_production_app()
