import runpy
from pathlib import Path


def test_memory_reconciliation_filters_test_events():
    path = Path(__file__).resolve().parents[2] / "scripts" / "reconcile_memory.py"
    should = runpy.run_path(str(path))["should_reconcile"]
    assert should("d019b377f2437e880a708c061c4924164d7f8e20") is True
    assert should("eval:20261027:identity-1") is False
    assert should("tool-fresh-order-test") is False
    assert should("approval-smoke-1") is False