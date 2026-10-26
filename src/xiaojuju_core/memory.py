import json, re, time
from pathlib import Path
from .paths import Paths
from .storage import append_jsonl

PATHS = Paths.production()

def memory_tokens(text: str) -> set[str]:
    text = (text or "").lower()
    tokens = set(re.findall(r"[a-z0-9_]{2,}", text))
    for run in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.update(run)
        tokens.update(run[i:i+2] for i in range(max(0, len(run)-1)))
    return tokens

def retrieve_memories(incoming: str, events_path: Path | None = None, limit: int = 4) -> list[dict]:
    path = Path(events_path) if events_path else PATHS.memory_events
    if not path.exists():
        return []
    query = memory_tokens(incoming)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        text = (row.get("user", "") + " " + row.get("assistant", "")).strip()
        overlap = len(query & memory_tokens(text))
        importance = 0
        if any(k in text for k in ("创业", "项目", "失败", "目标", "公司", "直播", "感情", "分手")):
            importance += 1
        if len(text) > 100:
            importance += 1
        age_days = max(0, (time.time() - float(row.get("epoch", time.time()))) / 86400)
        recency = max(0, 2 - age_days / 14)
        rows.append((overlap * 4 + importance + recency, float(row.get("epoch", 0)), row))
    if not rows:
        return []
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    recent_ids = {id(r) for _, _, r in sorted(rows, key=lambda x: x[1], reverse=True)[:2]}
    selected = []
    for score, _, row in rows:
        if score > 0.5 or id(row) in recent_ids:
            selected.append(row)
        if len(selected) >= limit:
            break
    return selected

def append_memory_event(user_text: str, assistant_text: str, events_path: Path | None = None, contact: str = "大哥") -> None:
    path = Path(events_path) if events_path else PATHS.memory_events
    row = {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": time.time(),
        "contact": contact,
        "user": user_text,
        "assistant": assistant_text,
    }
    append_jsonl(path, row)