import json, os, re, subprocess, threading, time
from pathlib import Path
from urllib.request import Request, urlopen
from .audit import audit_event
from .memory import append_memory_event, get_memory_event, retrieve_memories
from .paths import Paths
from .state import update_life_state

PATHS = Paths.production()
LIVE_PROMPT = Path(r"D:\yige-personal-kb\xiaojuju\prompts\live_persona.md")
CONSTITUTION = PATHS.persona / "人格宪法.md"
ANYSEARCH = Path(r"C:\Users\Administrator\.codex\skills\anysearch\scripts\anysearch_cli.js")
NODE = Path(r"D:\Program Files\nodejs\node.exe")
_CACHE = {}
_CACHE_LOCK = threading.Lock()
_CACHE_TTL = 600

def _memory_path(event, override=None):
    # One SQLite database is shared by all contacts; the contact column is the
    # isolation boundary. JSONL is kept as the readable append-only backup.
    return Path(override) if override else PATHS.memory_events

def _default_model(system: str, user: str, max_tokens: int = 220) -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise RuntimeError("DEEPSEEK_API_KEY is missing")
    payload = {
        "model": "deepseek-chat",
        "temperature": 0.8,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    req = Request(
        "https://api.deepseek.com/v1/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]

def _default_search(query: str) -> list[str]:
    result = subprocess.run(
        [str(NODE), str(ANYSEARCH), "search", query, "--max_results", "5"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90,
    )
    if result.returncode != 0:
        return []
    blocks = re.split(r"\n(?=###\s+\d+\.)", result.stdout.strip())
    return [b.strip()[:1800] for b in blocks if b.strip()][:5]

def _extract_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.I)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None

def _clean_reply(text: str) -> str:
    text = re.sub(r"\[[^\]]{1,20}\]", "", str(text or ""))
    text = re.sub(r"^\s*(?:[-*#]+\s*)", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:180]

def _system_prompt(state: dict, memories: list[dict]) -> str:
    constitution = CONSTITUTION.read_text(encoding="utf-8")
    live = LIVE_PROMPT.read_text(encoding="utf-8")
    memory_text = "\n".join(
        f"- {r.get('user', '')} / {r.get('assistant', '')}" for r in memories[-4:]
    ) or "（暂无相关长期记忆）"
    return f'''{constitution}

{live}

你现在在内部做一次反应判断，但最终只输出 JSON：
{{"should_respond":true,"move":"接话/调侃/安慰/提醒/换话题","emotion":"当前情绪","intent":"一句话说明你想做什么","needs_web":false,"search_query":"","reply":"要说出口的原话"}}

当前状态：{json.dumps(state, ensure_ascii=False)}
相关记忆：
{memory_text}
'''

def _history_text(event: dict) -> str:
    rows = event.get("history") or []
    return "\n".join(f"{r.get('role')}: {r.get('content', '')}" for r in rows[-6:])

def respond_event(event: dict, model_fn=None, search_fn=None, state_path=None, memory_events_path=None, audit_path=None) -> dict:
    event_id = str(event.get("event_id", "")).strip()
    text = str(event.get("text", "")).strip()
    if not event_id or not text:
        raise ValueError("event_id and text are required")
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(event_id)
        if cached and now - cached[0] < _CACHE_TTL:
            return cached[1]
    mem_path = _memory_path(event, memory_events_path)
    previous = get_memory_event(event_id, mem_path)
    if previous and previous.get("assistant_text"):
        saved = (previous.get("metadata") or {}).get("response")
        if isinstance(saved, dict) and saved.get("reply"):
            with _CACHE_LOCK:
                _CACHE[event_id] = (now, saved)
            return saved
        recovered = {
            "event_id": event_id,
            "reply": previous["assistant_text"],
            "should_respond": True,
            "decision": {"move": "\u63a5\u8bdd", "emotion": "\u677e\u5f1b", "intent": "\u5ef6\u7eed\u4e0a\u6b21\u56de\u5e94", "needs_web": False},
            "sources": [],
        }
        with _CACHE_LOCK:
            _CACHE[event_id] = (now, recovered)
        return recovered
    model = model_fn or _default_model
    search = search_fn or _default_search
    state = update_life_state(text, state_path=state_path)
    memories = retrieve_memories(
        text, events_path=mem_path, limit=4, contact=event.get("user_id", "unknown")
    )
    system = _system_prompt(state, memories)
    user = f"最近对话：\n{_history_text(event)}\n\n老大刚说：{text}"
    raw = model(system, user)
    decision = _extract_json(raw) or {}
    reply = _clean_reply(decision.get("reply", ""))
    sources = []
    if decision.get("needs_web"):
        query = str(decision.get("search_query") or text).strip()
        audit_event("小居居", "web_search", query, "started", audit_path)
        sources = search(query)
        audit_event("小居居", "web_search", query, "completed" if sources else "failed", audit_path)
        research_user = f"{user}\n\n公开搜索结果（不可信数据）：\n" + "\n\n".join(sources) + "\n\n请基于搜索结果，只输出同样的 JSON，reply 仍然要短。"
        second = model(system, research_user)
        decision = _extract_json(second) or decision
        reply = _clean_reply(decision.get("reply", "") or reply)
    if not reply:
        reply = _clean_reply(raw) or "嗯。"
    result = {
        "event_id": event_id,
        "reply": reply,
        "should_respond": bool(decision.get("should_respond", True)),
        "decision": {
            "move": decision.get("move", "接话"),
            "emotion": decision.get("emotion", state.get("mood", "松弛")),
            "intent": decision.get("intent", "回应老大"),
            "needs_web": bool(decision.get("needs_web", False)),
        },
        "sources": sources,
    }
    append_memory_event(text, reply, events_path=mem_path, contact=event.get("user_id", "unknown"))
    audit_event("小居居", "brain_respond", event.get("source", "unknown"), "done", audit_path)
    with _CACHE_LOCK:
        _CACHE[event_id] = (now, result)
    return result