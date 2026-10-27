import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from xiaojuju_core.daemon import tick
from xiaojuju_core.event_bus import EventBus
from xiaojuju_core.goals import add_goal
from xiaojuju_core.paths import Paths


def make_paths(root):
    return Paths(
        root,
        root / "persona",
        root / "state.json",
        root / "events.jsonl",
        root / "goals.json",
        root / "plans",
        root / "activities",
        root / "output",
        root / "reflection",
        root / "audit.jsonl",
        root / "paused.flag",
    )


class DaemonRetryTests(unittest.TestCase):
    def test_failed_cached_autonomy_is_retried(self):
        with tempfile.TemporaryDirectory() as d:
            paths = make_paths(Path(d))
            paths.daily_plans.mkdir(parents=True)
            goal = add_goal("research live", "self", 10, goals_path=paths.goals)
            bus_id = "autonomy:" + goal["id"]
            with EventBus(paths.event_bus) as bus:
                bus.enqueue(bus_id, "autonomy.task", {"goal": goal}, priority=20)
                bus.complete(
                    bus_id,
                    {"status": "failed", "result": {"status": "failed", "error": "empty"}},
                )

            out = tick(
                paths,
                datetime(2026, 10, 26, 10, 0),
                lambda prompt: {"title": "research live result", "markdown": "done"},
            )

            self.assertEqual(out["status"], "done")
