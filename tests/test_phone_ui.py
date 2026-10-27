import unittest

from xiaojuju_core.phone_ui import (
    append_history_message,
    composer_has_content,
    extract_current_ime,
    find_ocr_point,
    join_ocr_text,
    join_pending_messages,
    ocr_contains,
    outgoing_send_confirmed,
    pending_left_after_last_right,
)


class PhoneUiTests(unittest.TestCase):
    def test_send_label_uses_original_screenshot_coordinates(self):
        result = [
            ([[100, 1410], [210, 1410], [210, 1460], [100, 1460]], "发送", 0.92),
        ]
        self.assertEqual(find_ocr_point(result, "发送"), (155, 1435))

    def test_ocr_verification_normalizes_chinese_punctuation(self):
        result = [([[0, 0], [10, 0], [10, 10], [0, 10]], "收到，马上处理。", 0.88)]
        self.assertTrue(ocr_contains(result, "收到马上处理"))
        self.assertTrue(ocr_contains(result, "前文很长但是收到马上处理"))
        self.assertIn("收到", join_ocr_text(result))

    def test_ocr_tolerates_one_dropped_repeated_character(self):
        result = [([[0, 0], [10, 0], [10, 10], [0, 10]], "xj-test发送", 0.88)]
        self.assertTrue(ocr_contains(result, "xjj-test"))

    def test_composer_accepts_ocr_poor_text_with_send_affordance(self):
        self.assertTrue(composer_has_content(False, True, True))
        self.assertFalse(composer_has_content(False, True, False))
        self.assertTrue(composer_has_content(True, False, False))

    def test_outgoing_send_requires_composer_clear_and_focus(self):
        self.assertTrue(outgoing_send_confirmed(False, True))
        self.assertFalse(outgoing_send_confirmed(True, True))
        self.assertFalse(outgoing_send_confirmed(False, False))

    def test_current_ime_is_read_from_dumpsys(self):
        output = "mCurMethodId=com.android.adbkeyboard/.AdbIME\nmInputShown=true"
        self.assertEqual(extract_current_ime(output), "com.android.adbkeyboard/.AdbIME")

    def test_only_messages_after_last_outgoing_are_pending(self):
        messages = [
            {"side": "left", "text": "old question", "y": 1},
            {"side": "right", "text": "old answer", "y": 2},
            {"side": "left", "text": "first pending", "y": 3},
            {"side": "left", "text": "second pending", "y": 4},
        ]
        pending = pending_left_after_last_right(messages)
        self.assertEqual([item["text"] for item in pending], ["first pending", "second pending"])
        self.assertEqual(
            join_pending_messages(pending),
            "first pending\nsecond pending",
        )

    def test_history_append_is_bounded_and_role_preserving(self):
        history = []
        for index in range(25):
            append_history_message(history, "assistant", f"m{index}", at=float(index), limit=20)
        self.assertEqual(len(history), 20)
        self.assertEqual(history[0]["text"], "m5")
        self.assertEqual(history[-1]["text"], "m24")
        self.assertEqual(history[-1]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
