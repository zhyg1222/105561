import json, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from .pipeline import process_event

def extract_last_user_text(payload: dict) -> str:
    for msg in reversed(payload.get("messages", [])):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return "".join(str(x.get("text", "")) for x in content if isinstance(x, dict) and x.get("type") == "text")
    return ""

def _history(payload: dict) -> list[dict]:
    rows = []
    for msg in payload.get("messages", []):
        content = msg.get("content", "")
        if isinstance(content, list):
            content = "".join(str(x.get("text", "")) for x in content if isinstance(x, dict) and x.get("type") == "text")
        if msg.get("role") in {"user", "assistant"} and content:
            rows.append({"role": msg["role"], "content": str(content)})
    return rows[-8:]

def _event(payload: dict, headers=None) -> dict:
    text = extract_last_user_text(payload)
    headers = headers or {}
    return {
        "event_id": headers.get("Idempotency-Key") or uuid.uuid4().hex,
        "source": headers.get("X-XiaoJuJu-Source", "live"),
        "user_id": headers.get("X-XiaoJuJu-User", "local"),
        "scope": "public" if headers.get("X-XiaoJuJu-Source") == "live" else "private",
        "text": text,
        "history": _history(payload),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

def chat_completion_payload(payload: dict, responder=process_event) -> dict:
    event = _event(payload)
    result = responder(event)
    return {
        "id": "chatcmpl-" + event["event_id"],
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.get("model", "xiaojuju"),
        "choices": [{"index": 0, "message": {"role": "assistant", "content": result.get("reply", "")}, "finish_reason": "stop"}],
    }

def sse_lines(text: str, model: str = "xiaojuju", event_id: str | None = None):
    event_id = event_id or uuid.uuid4().hex
    base = {"id": "chatcmpl-" + event_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": model}
    for i in range(0, len(text), 8):
        chunk = dict(base)
        chunk["choices"] = [{"index": 0, "delta": {"content": text[i:i+8]}, "finish_reason": None}]
        yield "data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n"
    end = dict(base)
    end["choices"] = [{"index": 0, "delta": {}, "finish_reason": "stop"}]
    yield "data: " + json.dumps(end, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"

class Handler(BaseHTTPRequestHandler):
    responder = staticmethod(process_event)
    def log_message(self, fmt, *args):
        return
    def _send_json(self, code, data):
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type","application/json; charset=utf-8"); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Content-Length",str(len(raw))); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        if urlparse(self.path).path == "/health": self._send_json(200,{"status":"ok"})
        else: self._send_json(404,{"error":"not found"})
    def do_OPTIONS(self):
        self.send_response(204); self.send_header("Access-Control-Allow-Origin","*"); self.send_header("Access-Control-Allow-Headers","*"); self.send_header("Access-Control-Allow-Methods","GET,POST,OPTIONS"); self.end_headers()
    def do_POST(self):
        try:
            length=int(self.headers.get("Content-Length","0")); payload=json.loads(self.rfile.read(length) or b"{}")
            path=urlparse(self.path).path
            if path == "/v1/respond":
                event=payload; result=self.responder(event); self._send_json(200,result); return
            if path == "/v1/chat/completions":
                if not extract_last_user_text(payload): self._send_json(400,{"error":"missing user text"}); return
                event=_event(payload,self.headers); result=self.responder(event); reply=result.get("reply","")
                if payload.get("stream"):
                    self.send_response(200); self.send_header("Content-Type","text/event-stream; charset=utf-8"); self.send_header("Cache-Control","no-cache"); self.send_header("Access-Control-Allow-Origin","*"); self.end_headers()
                    for line in sse_lines(reply,payload.get("model","xiaojuju"),event["event_id"]): self.wfile.write(line.encode("utf-8")); self.wfile.flush()
                else:
                    self._send_json(200,{"id":"chatcmpl-"+event["event_id"],"object":"chat.completion","created":int(time.time()),"model":payload.get("model","xiaojuju"),"choices":[{"index":0,"message":{"role":"assistant","content":reply},"finish_reason":"stop"}]})
                return
            self._send_json(404,{"error":"not found"})
        except Exception as e:
            self._send_json(500,{"error":str(e)})

def serve(host="127.0.0.1", port=12400):
    server=ThreadingHTTPServer((host,port),Handler)
    server.serve_forever()