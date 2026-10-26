import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "replay_shadow", Path(__file__).resolve().parents[2] / "scripts" / "replay_shadow.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
make_shadow_event = module.make_shadow_event
request_headers = module.request_headers


def test_shadow_event_is_stable_and_uses_shadow_namespace():
    row = {"contact": "owner", "user": "hello", "assistant": "old", "epoch": 1.0}
    first = make_shadow_event(row)
    second = make_shadow_event(row)
    headers = request_headers(first)

    assert first.event_id == second.event_id
    assert first.shadow is True
    assert first.source == "shadow"
    assert headers["X-XiaoJuJu-Source"] == "shadow"
    assert headers["Idempotency-Key"] == first.event_id
