import tempfile, unittest
from pathlib import Path
from xiaojuju_core.event_bus import EventBus

class EventBusTests(unittest.TestCase):
    def test_priority_and_done(self):
        with tempfile.TemporaryDirectory() as d:
            b=EventBus(Path(d)/"events.db")
            b.enqueue("low","timer",{"x":1},priority=1,event_id="low")
            b.enqueue("high","user",{"x":2},priority=10,event_id="high")
            event=b.claim_next()
            self.assertEqual(event["event_id"],"high")
            b.complete(event["event_id"])
            self.assertEqual(b.claim_next()["event_id"],"low")
            b.close()
    def test_duplicate_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            b=EventBus(Path(d)/"events.db")
            self.assertTrue(b.enqueue("x","test",{},event_id="same"))
            self.assertFalse(b.enqueue("x","test",{},event_id="same"))
            self.assertEqual(b.stats()["queued"],1)
            b.close()
    def test_failure_can_retry(self):
        with tempfile.TemporaryDirectory() as d:
            b=EventBus(Path(d)/"events.db")
            b.enqueue("x","test",{},event_id="e1")
            e=b.claim_next(); b.fail(e["event_id"],"boom",retry=True)
            e=b.claim_next()
            self.assertEqual(e["event_id"],"e1")
            self.assertEqual(e["attempts"],1)
            b.close()