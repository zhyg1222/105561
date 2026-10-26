import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "replay_shadow", Path(__file__).resolve().parents[2] / "scripts" / "replay_shadow.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
make_shadow_event = module.make_shadow_event


def test_shadow_event_is_stable_and_never_sendable():
    row = {"contact": "owner", "user": "你好", "assistant": "旧回复", "epoch": 1.0}
    first = make_shadow_event(row)
    second = make_shadow_event(row)
    assert first.event_id == second.event_id
    assert first.shadow is True
    assert first.source == "shadow"
