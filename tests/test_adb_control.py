import unittest
from xiaojuju_core.adb_control import select_serial

class AdbControlTests(unittest.TestCase):
    def test_usb_only_ignores_wireless(self):
        text="abc\tdevice\n192.168.0.14:5555\tdevice"
        self.assertEqual(select_serial(text,"usb_only","abc","192.168.0.14:5555",True),"abc")
    def test_usb_only_returns_none_without_usb(self):
        text="192.168.0.14:5555\tdevice"
        self.assertIsNone(select_serial(text,"usb_only","abc","192.168.0.14:5555",True))
    def test_wireless_only(self):
        text="abc\tdevice\n192.168.0.14:5555\tdevice"
        self.assertEqual(select_serial(text,"wireless_only","abc","192.168.0.14:5555",True),"192.168.0.14:5555")