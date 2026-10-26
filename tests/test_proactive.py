import json, unittest
from datetime import datetime, timedelta, timezone
from xiaojuju_core.proactive import can_send, parse_proactive

CFG={"enabled":True,"allowed_hours":["09:00","22:00"],"max_per_day":2,"min_hours_between":3,"min_minutes_after_user_message":120,"style":"casual","no_formal_reports":True}

class ProactiveTests(unittest.TestCase):
    def test_quiet_hours_and_recent_user_block(self):
        now=datetime(2026,10,26,23,0)
        ok, reason=can_send(now,{},CFG,last_user_at=None,last_sent_at=None,daily_count=0,pending=0)
        self.assertFalse(ok); self.assertEqual(reason,"outside_hours")
        now=datetime(2026,10,26,12,0)
        ok, reason=can_send(now,{},CFG,last_user_at=now-timedelta(minutes=30),last_sent_at=None,daily_count=0,pending=0)
        self.assertFalse(ok); self.assertEqual(reason,"recent_user_chat")
    def test_limits_and_pending_block(self):
        now=datetime(2026,10,26,15,0)
        self.assertFalse(can_send(now,{},CFG,None,None,2,0)[0])
        self.assertFalse(can_send(now,{},CFG,None,None,0,1)[0])
        last=now-timedelta(hours=1)
        self.assertFalse(can_send(now,{},CFG,None,last,0,0)[0])
    def test_parse_proactive_message(self):
        raw=json.dumps({"should_send":True,"message":"刚想到个事，想跟你说两句。","reason":"有自然话题"},ensure_ascii=False)
        out=parse_proactive(raw)
        self.assertTrue(out["should_send"])
        self.assertIn("刚想到",out["message"])
    def test_overlong_or_report_like_message_is_rejected(self):
        raw=json.dumps({"should_send":True,"message":"# 今日报告\n"+"很长"*100,"reason":"汇报"},ensure_ascii=False)
        out=parse_proactive(raw)
        self.assertFalse(out["should_send"])