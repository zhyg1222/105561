import json, tempfile, unittest
from pathlib import Path
from xiaojuju_core.brain import PATHS, _memory_path, respond_event

class BrainTests(unittest.TestCase):
    def test_all_contacts_share_the_central_memory_database(self):
        event={"source":"wechat","user_id":"guest"}
        self.assertEqual(_memory_path(event), PATHS.memory_events)

    def test_reply_updates_state_and_memory(self):
        calls=[]
        def model(system,user):
            calls.append(user)
            return json.dumps({"should_respond":True,"move":"接话","emotion":"松弛","intent":"回应","needs_web":False,"search_query":"","reply":"行，知道了。"},ensure_ascii=False)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); state=root/"state.json"; mem=root/"mem.jsonl"; audit=root/"audit.jsonl"
            event={"event_id":"e1","source":"wechat","user_id":"u1","text":"随便聊聊","scope":"private","timestamp":"2026-10-26 11:00:00"}
            out=respond_event(event,model_fn=model,state_path=state,memory_events_path=mem,audit_path=audit)
            self.assertEqual(out["reply"],"行，知道了。")
            self.assertEqual(len(calls),1)
            self.assertTrue(mem.exists())
            self.assertEqual(json.loads(mem.read_text(encoding="utf-8").splitlines()[0])["user"],"随便聊聊")
    def test_same_event_is_idempotent(self):
        calls=[]
        def model(system,user):
            calls.append(1)
            return '{"should_respond":true,"move":"接话","emotion":"平稳","intent":"回应","needs_web":false,"search_query":"","reply":"嗯。"}'
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); kw=dict(model_fn=model,state_path=root/"s.json",memory_events_path=root/"m.jsonl",audit_path=root/"a.jsonl")
            event={"event_id":"same","source":"live","user_id":"viewer","text":"你好","scope":"public","timestamp":"2026-10-26 11:01:00"}
            a=respond_event(event,**kw); b=respond_event(event,**kw)
            self.assertEqual(a,b)
            self.assertEqual(len(calls),1)
    def test_web_decision_uses_search_context(self):
        calls=[]
        def model(system,user):
            calls.append(user)
            if len(calls)==1:
                return '{"should_respond":true,"move":"查证","emotion":"认真","intent":"查资料","needs_web":true,"search_query":"DeepSeek Harness","reply":""}'
            return '{"should_respond":true,"move":"回答","emotion":"认真","intent":"给出结论","needs_web":false,"search_query":"","reply":"官网是这个。"}'
        def search(query):
            self.assertEqual(query,"DeepSeek Harness")
            return ["https://github.com/deepseek-ai/deepseek-harness"]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            event={"event_id":"e2","source":"wechat","user_id":"u1","text":"查一下 DeepSeek Harness","scope":"private","timestamp":"2026-10-26 11:02:00"}
            out=respond_event(event,model_fn=model,search_fn=search,state_path=root/"s.json",memory_events_path=root/"m.jsonl",audit_path=root/"a.jsonl")
            self.assertEqual(out["reply"],"官网是这个。")
            self.assertEqual(len(calls),2)
            self.assertTrue(any("github.com/deepseek-ai/deepseek-harness" in s for s in out["sources"]))