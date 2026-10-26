import json, tempfile, unittest
from pathlib import Path
from xiaojuju_core.config import deep_merge, load_config, validate_config

BASE={"identity":{"display_name":"小居居","ai_label":"AI智能体"},"browser":{"private_network":False,"public_http":True},"social":{"unknown_contacts":"do_not_reply"},"autonomy":{"activity_limit_per_day":4,"activity_gap_minutes":120,"quiet_hours":["00:00","07:30"]},"publishing":{"ai_label_required":True,"require_human_review_for_sensitive":True}}

class ConfigTests(unittest.TestCase):
    def test_deep_merge_keeps_nested_defaults(self):
        merged=deep_merge(BASE,{"identity":{"display_name":"测试"},"autonomy":{"activity_limit_per_day":2}})
        self.assertEqual(merged["identity"]["ai_label"],"AI智能体")
        self.assertEqual(merged["identity"]["display_name"],"测试")
        self.assertEqual(merged["autonomy"]["activity_limit_per_day"],2)
    def test_load_config_merges_private(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); base=root/"base.json"; private=root/"private.json"
            base.write_text(json.dumps(BASE,ensure_ascii=False),encoding="utf-8")
            private.write_text(json.dumps({"identity":{"display_name":"小居居"}},ensure_ascii=False),encoding="utf-8")
            self.assertEqual(load_config(base,private)["identity"]["ai_label"],"AI智能体")
    def test_validation_rejects_unlabeled_or_private_network(self):
        bad=deep_merge(BASE,{"identity":{"ai_label":""}})
        with self.assertRaises(ValueError): validate_config(bad)
        bad=deep_merge(BASE,{"browser":{"private_network":True}})
        with self.assertRaises(ValueError): validate_config(bad)
        bad=deep_merge(BASE,{"social":{"unknown_contacts":"reply_all"}})
        with self.assertRaises(ValueError): validate_config(bad)