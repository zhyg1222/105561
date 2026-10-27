import asyncio
import logging
import sys
from contextlib import AsyncExitStack, suppress

from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from .db import Database
from .events import EventProcessing, EventStore
from .graph.conversation import build_conversation_graph
from .identity import IdentityBundle
from .memory import MemoryProvider, NullMemoryProvider, format_memory_context
from .settings import Settings

logger = logging.getLogger(__name__)

if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class AgentRuntime:
    def __init__(
        self, settings: Settings, memory_provider: MemoryProvider | None = None, tools=None
    ):
        self.settings = settings
        self.memory_provider = memory_provider or NullMemoryProvider()
        self.tools = tools or []
        self.stack = AsyncExitStack()
        self._start_lock = asyncio.Lock()
        self._started = False
        self.db: Database | None = None
        self.store: EventStore | None = None
        self.graph = None

    async def start(self) -> None:
        async with self._start_lock:
            if self._started:
                return
            db = Database(self.settings)
            self.db = db
            self.store = EventStore(db)
            try:
                await db.open()
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
                    timeout=60,
                    **model_kwargs,
                )
                identity = IdentityBundle.load(self.settings.identity_dir)
                self.graph = build_conversation_graph(model, saver, identity, tools=self.tools)
                self._started = True
            except Exception:
                await self.stack.aclose()
                self.stack = AsyncExitStack()
                with suppress(Exception):
                    await db.close()
                self.db = None
                self.store = None
                self.graph = None
                raise

    async def ensure_started(self) -> None:
        if not self._started:
            await self.start()

    async def stop(self) -> None:
        self._started = False
        await self.stack.aclose()
        self.stack = AsyncExitStack()
        if self.db is not None:
            with suppress(Exception):
                await self.db.close()
            self.db = None
            self.store = None
            self.graph = None

    async def reply(self, state: dict, thread_id: str) -> dict:
        await self.ensure_started()
        return await self.graph.ainvoke(state, {"configurable": {"thread_id": thread_id}})

    async def process_event(self, event_id: str) -> dict:
        await self.ensure_started()
        event = await self.store.get_event(event_id)
        if event is None:
            raise KeyError(event_id)
        if event["result"] is not None:
            return event["result"]

        claim = await self.store.claim_event(event_id)
        if claim is None:
            current = await self.store.get_event(event_id)
            if current and current["result"] is not None:
                return current["result"]
            raise EventProcessing(event_id)

        shadow = bool(claim["shadow"])
        contact = claim["contact_id"] or "unknown"
        user_text = str(claim["payload"].get("text", ""))
        raw_history = claim["payload"].get("history", [])
        history_context = "\n".join(
            f"{item.get('role', 'user')}: {item.get('content', '')}"
            for item in raw_history[-8:]
            if isinstance(item, dict) and item.get("content")
        )
        thread_id = f"{'shadow' if shadow else claim['source']}:{contact}"
        memory_provider = getattr(self, "memory_provider", NullMemoryProvider())
        try:
            memory_rows = await memory_provider.recall(contact, user_text)
            graph_result = await self.graph.ainvoke(
                {
                    "user_text": user_text,
                    "messages": [],
                    "trace_id": claim["trace_id"],
                    "memory_context": format_memory_context(memory_rows),
                    "history_context": history_context,
                },
                {"configurable": {"thread_id": thread_id}},
            )
            result = {
                "event_id": event_id,
                "reply": graph_result["reply"],
                "should_respond": True,
                "trace_id": claim["trace_id"],
                "identity_hash": graph_result.get("identity_hash", ""),
            }
            saved = await self.store.save_result(event_id, result, claim["claim_token"])
            if not saved:
                current = await self.store.get_event(event_id)
                if current and current["result"] is not None:
                    return current["result"]
                raise EventProcessing(event_id)
            if not shadow:
                try:
                    await memory_provider.remember(
                        contact,
                        user_text,
                        str(result["reply"]),
                        event_id=event_id,
                        source=str(claim["source"]),
                    )
                except Exception as exc:
                    logger.warning("memory write failed: %s", exc, exc_info=True)
            return result
        except Exception as exc:
            await self.store.release_claim(event_id, claim["claim_token"], repr(exc))
            raise
