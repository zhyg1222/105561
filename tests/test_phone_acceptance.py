import unittest
from xiaojuju_core.phone_acceptance import evaluate_phone

class PhoneAcceptanceTests(unittest.TestCase):
    def test_good_device_passes(self):
        r=evaluate_phone(connected=True,screenshot_ok=True,ocr_text_count=8,wechat_installed=True,battery_level=70,powered=True,ram_gb=6,android_sdk=31)
        self.assertTrue(r["passed"])
    def test_missing_wechat_or_ocr_fails(self):
        r=evaluate_phone(connected=True,screenshot_ok=True,ocr_text_count=0,wechat_installed=False,battery_level=70,powered=True,ram_gb=6,android_sdk=31)
        self.assertFalse(r["passed"])
        self.assertIn("wechat_not_installed",r["failures"])
        self.assertIn("screen_not_readable",r["failures"])
    def test_low_old_device_is_warning(self):
        r=evaluate_phone(connected=True,screenshot_ok=True,ocr_text_count=5,wechat_installed=True,battery_level=70,powered=True,ram_gb=4,android_sdk=27)
        self.assertTrue(r["passed"])
        self.assertIn("android_older_than_10",r["warnings"])