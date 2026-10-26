import json, tempfile, unittest
from pathlib import Path
from xiaojuju_core.memory_db import MemoryStore

class MemoryStoreTests(unittest.TestCase):
    def test_contact_isolation_and_recall(self):
        with tempfile.TemporaryDirectory() as d:
            s=MemoryStore(Path(d)/"memory.db")
            s.add_event("e1","大哥","wechat","直播怎么互动","先做实时回应")
            s.add_event("e2","阿明","wechat","今天吃什么","随便")
            rows=s.retrieve("大哥","直播",limit=5)
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]["user_text"],"直播怎么互动")
            s.close()
    def test_event_id_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            s=MemoryStore(Path(d)/"memory.db")
            self.assertTrue(s.add_event("e1","大哥","wechat","A","B"))
            self.assertFalse(s.add_event("e1","大哥","wechat","A","B"))
            self.assertEqual(s.event_count("大哥"),1)
            s.close()
    def test_relationship_update(self):
        with tempfile.TemporaryDirectory() as d:
            s=MemoryStore(Path(d)/"memory.db")
            s.update_relationship("大哥",familiarity=80,trust=70,notes="重要关系")
            r=s.relationship("大哥")
            self.assertEqual(r["familiarity"],80)
            self.assertEqual(r["notes"],"重要关系")
            s.close()
    def test_jsonl_migration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"events.jsonl"
            p.write_text(json.dumps({"time":"2026-10-26 10:00:00","epoch":1,"contact":"大哥","user":"旧消息","assistant":"旧回复"},ensure_ascii=False)+"\n",encoding="utf-8")
            s=MemoryStore(Path(d)/"memory.db")
            self.assertEqual(s.migrate_jsonl(p),1)
            self.assertEqual(s.event_count("大哥"),1)
            s.close()