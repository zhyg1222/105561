import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from tests.agent.helpers import FakeEventService, IdempotentProcessor
from xiaojuju_agent.api import create_app
from xiaojuju_agent.settings import Settings


def test_startup_survives_postgres_down():
    class DownRuntime:
        store = None
        db = None

        async def start(self):
            raise ConnectionError("postgres down")

        async def stop(self):
            return None

    settings = Settings(
        database_url="postgresql://unreachable",
        environment="test",
        valkey_url="redis://127.0.0.1:6379/0",
        opa_url="http://127.0.0.1:8181",
    )

    from xiaojuju_agent.main import create_production_app

    app = create_production_app(settings=settings, runtime=DownRuntime(), policy_client=None)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        response = client.post(
            "/v1/events",
            json={
                "event_id": "down-1",
                "source": "shadow",
                "kind": "message",
                "payload": {"text": "hello"},
                "trace_id": "trace-down",
                "shadow": True,
            },
        )
    assert response.status_code == 503


def test_event_ingestion_creates_span(span_exporter):
    exporter = span_exporter
    events = FakeEventService()
    app = create_app(
        events,
        IdempotentProcessor(),
        lambda event_id, traceparent: None,
        None,
        force_shadow=True,
    )
    body = {
        "event_id": "span-event",
        "source": "shadow",
        "kind": "message",
        "payload": {"text": "hello"},
        "trace_id": "trace-span",
        "shadow": True,
    }
    with TestClient(app) as client:
        assert client.post("/v1/events", json=body).status_code == 202
    spans = [span for span in exporter.get_finished_spans() if span.name == "event.ingest"]
    assert spans and spans[-1].attributes["event_id"] == "span-event"


def test_worker_creates_process_span(monkeypatch, span_exporter):
    from xiaojuju_agent import queue_app

    async def completes(event_id):
        return {"event_id": event_id, "reply": "ok"}

    monkeypatch.setattr(queue_app, "_run", completes)
    exporter = span_exporter

    queue_app.process_event.run("worker-span")

    spans = [span for span in exporter.get_finished_spans() if span.name == "event.process"]
    assert spans and spans[-1].attributes["event_id"] == "worker-span"


def test_agent_env_is_ignored():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "--no-index", "deploy/agent.env"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0


def test_runbook_uses_binary_safe_backup():
    text = Path("docs/runbooks/agent-platform.md").read_text(encoding="utf-8")
    assert "pg_dump -Fc -f" in text
    assert "pg_dump -Fc -U" not in text


import asyncio

import pytest

from xiaojuju_agent.contracts import IncomingEvent
from xiaojuju_agent.events import EventProcessing
from xiaojuju_agent.runtime import AgentRuntime


class CountingGraph:
    def __init__(self, gate=None):
        self.calls = 0
        self.configs = []
        self.gate = gate

    async def ainvoke(self, state, config):
        self.calls += 1
        self.configs.append(config)
        if self.gate is not None:
            self.gate.set()
            await asyncio.sleep(0.05)
        return {"reply": f"reply-{self.calls}", "identity_hash": "identity"}


def runtime_with(store, graph):
    runtime = object.__new__(AgentRuntime)
    runtime.store = store
    runtime.graph = graph
    runtime._started = True
    return runtime


@pytest.mark.asyncio
async def test_runtime_claim_is_exclusive_and_shadow_isolated(event_store):
    event = IncomingEvent(
        event_id="runtime-shadow",
        source="shadow",
        kind="message",
        contact_id="owner",
        payload={"text": "hello"},
        trace_id="trace-runtime",
        shadow=True,
    )
    await event_store.insert_event(event)
    gate = asyncio.Event()
    graph = CountingGraph(gate=gate)
    runtime = runtime_with(event_store, graph)

    first = asyncio.create_task(runtime.process_event(event.event_id))
    await gate.wait()
    second = asyncio.create_task(runtime.process_event(event.event_id))
    results = await asyncio.gather(first, second, return_exceptions=True)

    assert graph.calls == 1
    assert graph.configs[0]["configurable"]["thread_id"] == "shadow:owner"
    assert sum(isinstance(item, EventProcessing) for item in results) == 1


@pytest.mark.asyncio
async def test_completed_event_survives_process_restart_without_model_call(event_store):
    event = IncomingEvent(
        event_id="runtime-restart",
        source="shadow",
        kind="message",
        contact_id="owner",
        payload={"text": "hello"},
        trace_id="trace-restart",
        shadow=True,
    )
    await event_store.insert_event(event)
    first_graph = CountingGraph()
    first = await runtime_with(event_store, first_graph).process_event(event.event_id)

    second_graph = CountingGraph()
    second = await runtime_with(event_store, second_graph).process_event(event.event_id)

    assert first == second
    assert first_graph.calls == 1
    assert second_graph.calls == 0


from httpx import ASGITransport, AsyncClient

from xiaojuju_agent.events import EventService


@pytest.mark.asyncio
async def test_chat_api_is_idempotent_with_real_event_store(event_store):
    graph = CountingGraph()
    runtime = runtime_with(event_store, graph)
    app = create_app(
        EventService(event_store),
        runtime.process_event,
        lambda event_id: None,
        None,
        force_shadow=True,
    )
    body = {"messages": [{"role": "user", "content": "hello"}], "model": "xiaojuju"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post(
            "/v1/chat/completions", json=body, headers={"Idempotency-Key": "real-chat"}
        )
        second = await client.post(
            "/v1/chat/completions", json=body, headers={"Idempotency-Key": "real-chat"}
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["choices"][0]["message"]["content"] == "reply-1"
    assert second.json()["choices"][0]["message"]["content"] == "reply-1"
    assert graph.calls == 1
