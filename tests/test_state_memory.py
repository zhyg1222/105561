import json, tempfile, time, unittest
from pathlib import Path
from xiaojuju_core.state import update_life_state
from xiaojuju_core.memory import append_memory_event, retrieve_memories

class StateMemoryTests(unittest.TestCase):
    def test_state_decays_and_tracks_topic(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            s = update_life_state("今天有点累，但想聊项目", state_path=p)
            self.assertEqual(s["mood"], "收着劲，先听你说")
            self.assertEqual(s["interactions_today"], 1)
            self.assertLess(s["social_battery"], 80)
    def test_relevant_memory_is_retrieved(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "events.jsonl"
            append_memory_event("直播应该怎么做", "先做实时互动", events_path=p)
            append_memory_event("今天吃什么", "随便吃点", events_path=p)
            rows = retrieve_memories("你还记得直播吗", events_path=p, limit=1)
            self.assertEqual(rows[0]["user"], "直播应该怎么做")