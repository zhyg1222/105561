import json, tempfile, unittest
from pathlib import Path
from xiaojuju_core.permissions import check_permission
from xiaojuju_core.audit import audit_event

class PermissionAuditTests(unittest.TestCase):
    def test_public_read_allowed_and_spend_denied(self):
        self.assertEqual(check_permission("web_search")[0], "allow")
        self.assertEqual(check_permission("spend_money")[0], "deny")
    def test_external_message_requires_ask(self):
        self.assertEqual(check_permission("send_message", "self")[0], "ask")
    def test_audit_row_is_jsonl(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "audit.jsonl"
            audit_event("小居居", "web_search", "public", "completed", p)
            self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["action"], "web_search")