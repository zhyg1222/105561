from fastapi.testclient import TestClient
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from xiaojuju_agent.api import create_app
from xiaojuju_agent.events import SubmitResult


class FakeGraph:
    async def ainvoke(self, state, config):
        return {"reply": "ok", "messages": []}


class FakeEvents:
    async def submit(self, event, dispatch):
        return SubmitResult(True, "received", True)


def test_trace_id_is_attached_to_reply():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    app = create_app(FakeEvents(), FakeGraph(), lambda event_id: None, None)
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "xiaojuju", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 200
    spans = [span for span in exporter.get_finished_spans() if span.name == "chat.completion"]
    assert spans and spans[-1].attributes["event_id"]


def test_readyz_returns_503_without_dependencies():
    app = create_app(FakeEvents(), FakeGraph(), lambda event_id: None, None)
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgres": False, "opa": False}
