import tempfile, unittest
from pathlib import Path
from xiaojuju_core.identity import load_public_identity, assert_no_secret_fields

class IdentityTests(unittest.TestCase):
    def test_loads_name_and_accounts(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"accounts.json"
            p.write_text('{"display_name":"小居居","ai_label":"AI智能体","accounts":[]}',encoding="utf-8")
            self.assertEqual(load_public_identity(p)["display_name"],"小居居")
    def test_rejects_secret_fields(self):
        with self.assertRaises(ValueError):
            assert_no_secret_fields({"accounts":[{"platform":"x","token":"secret"}]})

class AiLabelTests(unittest.TestCase):
    def test_ai_label_is_mandatory(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'accounts.json'
            p.write_text('{"display_name":"小居居","ai_label":"AI智能体","accounts":[]}',encoding='utf-8')
            self.assertEqual(load_public_identity(p)['ai_label'],'AI智能体')
            p.write_text('{"display_name":"小居居","accounts":[]}',encoding='utf-8')
            with self.assertRaises(ValueError):
                load_public_identity(p)