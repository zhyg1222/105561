import asyncio
import importlib.util
import uuid
from pathlib import Path

import fasteners
import pgserver
import pgserver.postgres_server as pgserver_module
import pytest
import pytest_asyncio
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pgserver.postgres_server import PostgresServer

from xiaojuju_agent.api import create_app
from xiaojuju_agent.db import Database
from xiaojuju_agent.events import EventStore, SubmitResult
from xiaojuju_agent.settings import Settings

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def pg_container():
    runtime = Path("D:/yige-personal-kb/.runtime/agent-tests")
    runtime.mkdir(parents=True, exist_ok=True)
    lock_dir = runtime / "pgserver-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    PostgresServer.runtime_path = lock_dir
    PostgresServer.lock_path = lock_dir / ".lockfile"
    PostgresServer._lock = fasteners.InterProcessLock(PostgresServer.lock_path)
    original_initdb = pgserver_module.initdb

    def initdb_with_c_locale(args, pgdata=None, **kwargs):
        return original_initdb([*args, "--locale=C"], pgdata=pgdata, **kwargs)

    pgserver_module.initdb = initdb_with_c_locale
    data_dir = runtime / f"pgdata-{uuid.uuid4().hex}"
    data_dir.mkdir(parents=True, exist_ok=False)
    server = pgserver.get_server(data_dir, cleanup_mode="stop")
    try:
        yield server
    finally:
        server.cleanup()


@pytest_asyncio.fixture
async def event_store(pg_container):
    settings = Settings(
        database_url=pg_container.get_uri(),
        valkey_url="valkey://127.0.0.1:6379/15",
        opa_url="http://127.0.0.1:8181",
        environment="test",
    )
    db = Database(settings)
    await db.open()
    spec = importlib.util.spec_from_file_location(
        "platform_migration", Path("migrations/versions/0001_platform.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    async with db.transaction() as conn:
        await module.upgrade(conn)
    try:
        yield EventStore(db)
    finally:
        await db.close()


@pytest_asyncio.fixture
async def postgres_saver(pg_container):
    manager = AsyncPostgresSaver.from_conn_string(pg_container.get_uri())
    saver = await manager.__aenter__()
    await saver.setup()
    try:
        yield saver
    finally:
        await manager.__aexit__(None, None, None)


class FakeGraph:
    async def ainvoke(self, state, config):
        return {"reply": "\u6536\u5230\uff1a" + state["user_text"], "messages": []}


class FakeEventService:
    async def submit(self, event, dispatch):
        return SubmitResult(True, "received", event.shadow)


class FailingEventService:
    async def submit(self, event, dispatch):
        raise ConnectionError("postgres down")


@pytest.fixture
def app():
    return create_app(
        FakeEventService(), FakeGraph(), dispatch=lambda event_id: None, policy_client=None
    )


@pytest.fixture
def failing_app():
    return create_app(
        FailingEventService(),
        FakeGraph(),
        dispatch=lambda event_id: None,
        policy_client=None,
    )
