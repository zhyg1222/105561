import asyncio
import sys
from contextlib import AsyncExitStack

from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .db import Database
from .events import EventStore
from .graph.conversation import build_conversation_graph
from .settings import Settings

if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class AgentRuntime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.stack = AsyncExitStack()
        self.db: Database | None = None
        self.store: EventStore | None = None
        self.graph = None

    async def start(self) -> None:
        self.db = Database(self.settings)
        await self.db.open()
        self.store = EventStore(self.db)
        saver = await self.stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(self.settings.database_url)
        )
        await saver.setup()
        model_kwargs = {}
        if self.settings.deepseek_api_key is not None:
            model_kwargs["api_key"] = self.settings.deepseek_api_key.get_secret_value()
        model = ChatDeepSeek(
            model="deepseek-chat",
            temperature=0.8,
            max_retries=2,
            **model_kwargs,
        )
        self.graph = build_conversation_graph(model, saver)

    async def stop(self) -> None:
        await self.stack.aclose()
        if self.db is not None:
            await self.db.close()

    async def reply(self, state: dict, thread_id: str) -> dict:
        return await self.graph.ainvoke(state, {"configurable": {"thread_id": thread_id}})

    async def process_event(self, event_id: str) -> dict:
        event = await self.store.get_event(event_id)
        if event is None:
            raise KeyError(event_id)
        if event["result"]:
            return event["result"]
        if event["shadow"]:
            return {"status": "shadow_ignored", "event_id": event_id}
        await self.store.mark_status(event_id, "processing")
        text = str(event["payload"].get("text", ""))
        graph_result = await self.reply(
            {"user_text": text, "messages": [], "trace_id": event["trace_id"]},
            f"{event['source']}:{event['contact_id'] or 'unknown'}",
        )
        result = {
            "event_id": event_id,
            "reply": graph_result["reply"],
            "should_respond": True,
            "trace_id": event["trace_id"],
        }
        await self.store.save_result(event_id, result)
        return result
