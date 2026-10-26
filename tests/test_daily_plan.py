import tempfile, unittest
from pathlib import Path
from xiaojuju_core.daily_plan import ensure_daily_plan, mark_plan_item

class DailyPlanTests(unittest.TestCase):
    def test_same_day_is_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            a = ensure_daily_plan("2026-10-26", p)
            b = ensure_daily_plan("2026-10-26", p)
            self.assertEqual(a, b)
            self.assertEqual(len(list(p.glob("*.json"))), 1)
    def test_mark_item_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            plan = ensure_daily_plan("2026-10-26", p)
            first = plan["items"][0]["id"]
            mark_plan_item("2026-10-26", first, "done", p)
            updated = mark_plan_item("2026-10-26", first, "done", p)
            self.assertEqual(updated["items"][0]["status"], "done")