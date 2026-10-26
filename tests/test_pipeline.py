import tempfile
import unittest
from pathlib import Path
from xiaojuju_core.event_bus import EventBus
from xiaojuju_core.pipeline import process_event


class PipelineTests(unittest.TestCase):
    def test_completed_event_returns_saved_reply_without_reprocessing(self):
        calls = []
        def responder(event):
            calls.append(event["event_id"])
            return {"event_id": event["event_id"], "reply": "saved", "should_respond": True}
        with tempfile.TemporaryDirectory() as d:
            bus_path = Path(d) / "bus.db"
            event = {"event_id": "same", "source": "wechat", "user_id": "u1", "text": "hello"}
            first = process_event(event, responder, bus_path=bus_path)
            second = process_event(event, responder, bus_path=bus_path)
            self.assertEqual(first, second)
            self.assertEqual(calls, ["same"])
            with EventBus(bus_path) as bus:
                self.assertEqual(bus.stats()["completed"], 1)

    def test_failed_event_is_requeued_and_can_retry(self):
        calls = []
        def responder(event):
            calls.append(event["event_id"])
            if len(calls) == 1:
                raise RuntimeError("temporary")
            return {"event_id": event["event_id"], "reply": "ok", "should_respond": True}
        with tempfile.TemporaryDirectory() as d:
            bus_path = Path(d) / "bus.db"
            event = {"event_id": "retry", "source": "wechat", "user_id": "u1", "text": "hello"}
            with self.assertRaises(RuntimeError):
                process_event(event, responder, bus_path=bus_path)
            with EventBus(bus_path) as bus:
                self.assertEqual(bus.stats()["queued"], 1)
            result = process_event(event, responder, bus_path=bus_path)
            self.assertEqual(result["reply"], "ok")
            self.assertEqual(len(calls), 2)
