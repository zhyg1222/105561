import tempfile, unittest
from pathlib import Path
from xiaojuju_core.goals import add_goal, next_goal, set_goal_status

class GoalTests(unittest.TestCase):
    def test_boss_goal_beats_self_goal(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "goals.json"
            add_goal("自己研究直播", "self", 50, goals_path=p)
            boss = add_goal("准备门店介绍", "boss", 50, goals_path=p)
            self.assertEqual(next_goal(p)["id"], boss["id"])
    def test_done_goal_is_not_selected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "goals.json"
            g = add_goal("查资料", "self", 10, goals_path=p)
            set_goal_status(g["id"], "done", "ok", goals_path=p)
            self.assertIsNone(next_goal(p))