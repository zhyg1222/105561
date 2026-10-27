import json, tempfile, unittest
from datetime import datetime
from pathlib import Path
from xiaojuju_core.daemon import tick
from xiaojuju_core.goals import add_goal
from xiaojuju_core.curiosity import add_interest
from xiaojuju_core.paths import Paths

def make_paths(root):
    return Paths(root, root/"persona", root/"state.json", root/"events.jsonl", root/"goals.json", root/"plans", root/"activities", root/"output", root/"reflection", root/"audit.jsonl", root/"paused.flag")

class DaemonTests(unittest.TestCase):
    def test_quiet_hours_skip(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            add_goal("研究直播", "self", 10, goals_path=p.goals)
            out = tick(p, datetime(2026,10,26,3,0), lambda prompt: {"title":"x","markdown":"x"})
            self.assertEqual(out["status"], "quiet_hours")
    def test_creates_self_goal_when_queue_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            runner = lambda prompt: {"title":"自主观察","markdown":"# 我看到的\n\n人们喜欢被认真回应。"}
            out = tick(p, datetime(2026,10,26,10,0), runner)
            self.assertEqual(out["status"], "done")
            data = json.loads(p.goals.read_text(encoding="utf-8"))
            self.assertEqual(data["goals"][0]["source"], "self")
            self.assertTrue(data["goals"][0]["title"])
    def test_one_activity_per_tick_and_gap(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            add_goal("研究直播", "self", 10, goals_path=p.goals)
            runner = lambda prompt: {"title":"研究直播","markdown":"# ok"}
            first = tick(p, datetime(2026,10,26,10,0), runner)
            add_goal("第二个目标", "self", 9, goals_path=p.goals)
            second = tick(p, datetime(2026,10,26,10,15), runner)
            self.assertEqual(first["status"], "done")
            self.assertEqual(second["status"], "activity_gap")
    def test_writes_reflection_at_night(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            add_goal("夜间研究", "self", 10, goals_path=p.goals)
            out = tick(p, datetime(2026,10,26,22,5), lambda prompt: {"title":"夜间成果","markdown":"完成"})
            self.assertEqual(out["status"], "done")
            reflection = Path(d) / "reflection" / "2026-10-26.md"
            self.assertTrue(reflection.exists())
            self.assertIn("夜间研究", reflection.read_text(encoding="utf-8"))
    def test_curiosity_queue_drives_self_goal(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            queue = p.persona / "自主生活" / "兴趣" / "关注队列.json"
            add_interest("虚拟主播如何自然接弹幕", "想改善直播互动", interests_path=queue)
            out = tick(p, datetime(2026,10,26,10,0), lambda prompt: {"title":"虚拟主播接弹幕研究结果","markdown":"完成"})
            self.assertEqual(out["status"], "done")
            data = json.loads(p.goals.read_text(encoding="utf-8"))
            self.assertIn("虚拟主播如何自然接弹幕", data["goals"][0]["title"])
            interests = json.loads(queue.read_text(encoding="utf-8"))
            self.assertEqual(interests["interests"][0]["status"], "done")
    def test_self_research_creates_followup_interest(self):
        with tempfile.TemporaryDirectory() as d:
            p = make_paths(Path(d)); p.daily_plans.mkdir(parents=True)
            queue = p.persona / "自主生活" / "兴趣" / "关注队列.json"
            add_interest("第一项研究", "起点", interests_path=queue)
            runner = lambda prompt: {"title":"第一项成果","markdown":"完成","follow_up":"下一项继续研究什么"}
            out = tick(p, datetime(2026,10,26,10,0), runner)
            self.assertEqual(out["status"], "done")
            data = json.loads(queue.read_text(encoding="utf-8"))
            topics = [x["topic"] for x in data["interests"]]
            self.assertIn("下一项继续研究什么", topics)
