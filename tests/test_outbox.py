import tempfile, unittest
from pathlib import Path
from xiaojuju_core.outbox import enqueue_message, pending_messages, mark_message

class OutboxTests(unittest.TestCase):
    def test_queue_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"outbox.json"
            m=enqueue_message("大哥","今日简报","money_brief",outbox_path=p)
            q=pending_messages(p)
            self.assertEqual(q[0]["text"],"今日简报")
            mark_message(m["id"],"sent",outbox_path=p)
            self.assertEqual(pending_messages(p),[])
    def test_empty_message_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                enqueue_message("大哥"," ","money_brief",outbox_path=Path(d)/"o.json")