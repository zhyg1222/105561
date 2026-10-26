import json, tempfile, unittest
from datetime import datetime
from pathlib import Path
from xiaojuju_core.daemon import tick
from xiaojuju_core.goals import add_goal
from xiaojuju_core.paths import Paths

class IntegrationTests(unittest.TestCase):
    def test_boss_task_runs_before_self_task(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=Paths(root,root/"persona",root/"state.json",root/"events.jsonl",root/"goals.json",root/"plans",root/"activities",root/"output",root/"reflection",root/"audit.jsonl",root/"paused.flag")
            p.daily_plans.mkdir(parents=True)
            add_goal("自主研究", "self", 99, goals_path=p.goals)
            boss=add_goal("老大任务", "boss", 1, goals_path=p.goals)
            out=tick(p, datetime(2026,10,26,10,0), lambda prompt: {"title":"完成","markdown":"成功"})
            self.assertEqual(out["status"],"done")
            data=json.loads(p.goals.read_text(encoding="utf-8"))
            self.assertEqual([g["status"] for g in data["goals"] if g["id"]==boss["id"]], ["done"])