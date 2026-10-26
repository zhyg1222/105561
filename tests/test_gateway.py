import json, unittest
from xiaojuju_core.gateway import extract_last_user_text, chat_completion_payload, sse_lines

class GatewayTests(unittest.TestCase):
    def test_extract_last_user_text(self):
        payload={"messages":[{"role":"system","content":"old"},{"role":"user","content":[{"type":"text","text":"你好"}]}]}
        self.assertEqual(extract_last_user_text(payload),"你好")
    def test_chat_completion_payload(self):
        responder=lambda event: {"event_id":event["event_id"],"reply":"我在。","should_respond":True,"decision":{},"sources":[]}
        payload={"model":"xiaojuju","messages":[{"role":"user","content":"在吗"}]}
        out=chat_completion_payload(payload,responder)
        self.assertEqual(out["choices"][0]["message"]["content"],"我在。")
    def test_sse_lines_end_with_done(self):
        chunks=list(sse_lines("我在。","xiaojuju"))
        self.assertTrue(any("我在" in x for x in chunks))
        self.assertEqual(chunks[-1],"data: [DONE]\n\n")