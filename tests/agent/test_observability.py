from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from tests.agent.helpers import FakeEventService, IdempotentProcessor
from xiaojuju_agent.api import create_app
from xiaojuju_agent.observability import configure_observability
from xiaojuju_agent.settings import Settings


def test_trace_id_is_attached_to_reply():
    exporter = InMemorySpanExporter()
    app = create_app(
        event_service=FakeEventService(),
        process_event=IdempotentProcessor(),
        dispatch=lambda event_id: None,
        policy_client=None,
        force_shadow=True,
    )
    provider = configure_observability(Settings(), app=app, force_exporter=True)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with TestClient(app) as client:
        response = client.post(
            "/v1/chat/completions",
            json={"model": "xiaojuju", "messages": [{"role": "user", "content": "hi"}]},
        )
    assert response.status_code == 200
    spans = [span for span in exporter.get_finished_spans() if span.name == "chat.completion"]
    assert spans and spans[-1].attributes["event_id"]


def test_readyz_returns_503_without_dependencies():
    app = create_app(
        event_service=FakeEventService(),
        process_event=IdempotentProcessor(),
        dispatch=lambda event_id: None,
        policy_client=None,
        force_shadow=True,
    )
    with TestClient(app) as client:
        response = client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["checks"] == {"postgres": False, "opa": False, "runtime": False}
