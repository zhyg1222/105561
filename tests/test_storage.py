import json, tempfile, unittest
from pathlib import Path
from xiaojuju_core.storage import atomic_write_json, read_json, append_jsonl
from xiaojuju_core.paths import Paths

class StorageTests(unittest.TestCase):
    def test_round_trip_and_append(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "state.json"
            atomic_write_json(p, {"energy": 70})
            self.assertEqual(read_json(p, {}), {"energy": 70})
            q = Path(d) / "events.jsonl"
            append_jsonl(q, {"id": 1}); append_jsonl(q, {"id": 2})
            self.assertEqual([json.loads(x)["id"] for x in q.read_text(encoding="utf-8").splitlines()], [1, 2])
    def test_bad_json_returns_default(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "bad.json"; p.write_text("{", encoding="utf-8")
            self.assertEqual(read_json(p, {"ok": True}), {"ok": True})
    def test_production_paths(self):
        p = Paths.production()
        self.assertEqual(p.persona, Path(r"D:\yige-personal-kb\12_社交代理\小居居"))
        self.assertEqual(p.state.name, "当前状态.json")