from pathlib import Path

import yaml


def test_lock_contains_required_versions():
    data = yaml.safe_load(Path("deploy/versions.lock").read_text(encoding="utf-8"))
    assert data["langgraph"] == "1.2.17"
    assert data["graphiti"] == "0.31.2"
    assert data["mobilerun"] == "0.7.2"
    assert data["browser_use"] == "0.13.13"
    assert data["opa"] == "1.21.4"
