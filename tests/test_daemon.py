import tempfile, unittest
from datetime import datetime
from pathlib import Path
from xiaojuju_core.daemon import tick
from xiaojuju_core.goals import add_goal
from xiaojuju_core.paths import Paths

def test_paths(root):
    return Paths(root, root/"persona", root/"state.json", root/"events.jsonl", root/"goals.json", root/"plans", root/"activities", root/"output", root/"reflection", root/"audit.jsonl", root/"paused.flag")

class DaemonTests(unittest.TestCase):
    def test_quiet_hours_skip(self):
        with tempfile.TemporaryDirectory() as d:
            p = test_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            add_goal("研究直播", "self", 10, goals_path=p.goals)
            out = tick(p, datetime(2026,10,26,3,0), lambda prompt: {"title":"x","markdown":"x"})
            self.assertEqual(out["status"], "quiet_hours")
    def test_one_activity_per_tick_and_gap(self):
        with tempfile.TemporaryDirectory() as d:
            p = test_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            add_goal("研究直播", "self", 10, goals_path=p.goals)
            runner = lambda prompt: {"title":"研究","markdown":"# ok"}
            first = tick(p, datetime(2026,10,26,10,0), runner)
            add_goal("第二个目标", "self", 9, goals_path=p.goals)
            second = tick(p, datetime(2026,10,26,10,15), runner)
            self.assertEqual(first["status"], "done")
            self.assertEqual(second["status"], "activity_gap")