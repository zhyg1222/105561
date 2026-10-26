import tempfile, unittest
from pathlib import Path
from xiaojuju_core.curiosity import add_interest, next_interest, mark_interest

class CuriosityTests(unittest.TestCase):
    def test_queue_is_persistent_and_consumable(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"interests.json"
            a=add_interest("AI如何保持人格一致", "想知道长期记忆怎么影响身份", interests_path=p)
            self.assertEqual(next_interest(p)["id"], a["id"])
            mark_interest(a["id"], "done", "已研究", interests_path=p)
            self.assertIsNone(next_interest(p))
    def test_empty_topic_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                add_interest("", "", interests_path=Path(d)/"i.json")