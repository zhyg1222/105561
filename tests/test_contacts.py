import json, tempfile, unittest
from pathlib import Path
from xiaojuju_core.contacts import load_wechat_contacts, contact_key

class ContactTests(unittest.TestCase):
    def test_only_enabled_contacts_are_loaded(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"contacts.json"
            p.write_text(json.dumps({"contacts":[{"name":"大哥","enabled":True},{"name":"阿明","enabled":False}]},ensure_ascii=False),encoding="utf-8")
            self.assertEqual([x["name"] for x in load_wechat_contacts(p)],["大哥"])
    def test_contact_key_is_stable_and_hides_name(self):
        self.assertEqual(contact_key("大哥"),contact_key("大哥"))
        self.assertNotIn("大哥",contact_key("大哥"))