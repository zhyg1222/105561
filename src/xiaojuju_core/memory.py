import json
import time
import uuid
from pathlib import Path
from .memory_db import MemoryStore, memory_tokens
from .paths import Paths
from .storage import append_jsonl

PATHS = Paths.production()
DEFAULT_CONTACT = "\u5927\u54e5"


def memory_db_path(events_path: Path | str | None = None) -> Path:
    path = Path(events_path) if events_path else PATHS.memory_events
    if path.name == "\u4e8b\u4ef6.jsonl" and path.parent.name == "\u8bb0\u5fc6":
        return path.parent / "\u8bb0\u5fc6.db"
    return path.with_suffix(".db")


def _store(events_path: Path | str | None = None) -> MemoryStore:
    path = Path(events_path) if events_path else PATHS.memory_events
    db_path = memory_db_path(path)
    db_existed = db_path.exists()
    store = MemoryStore(db_path)
    # Import once when the database is first created. New writes are dual-written
    # to SQLite and JSONL, so normal requests do not rescan historical logs.
    if not db_existed:
        if path.exists():
            store.migrate_jsonl(path)
        if events_path is None:
            legacy = path.parent / r"\u8bbf\u5ba2"
            if legacy.exists():
                for old_path in legacy.rglob("*.jsonl"):
                    store.migrate_jsonl(old_path)
    return store


def retrieve_memories(
    incoming: str,
    events_path: Path | None = None,
    limit: int = 4,
    contact: str | None = None,
) -> list[dict]:
    path = Path(events_path) if events_path else PATHS.memory_events
    contact = str(contact or DEFAULT_CONTACT)
    try:
        with _store(path) as store:
            return store.retrieve(contact, incoming, limit=limit)
    except Exception:
        # JSONL remains the readable backup and a last-resort read path.
        if not path.exists():
            return []
    query = memory_tokens(incoming)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("contact") or DEFAULT_CONTACT) != contact:
            continue
        text = (row.get("user", "") + " " + row.get("assistant", "")).strip()
        overlap = len(query & memory_tokens(text))
        importance = 0
        if any(k in text for k in ("\u521b\u4e1a", "\u9879\u76ee", "\u5931\u8d25", "\u76ee\u6807", "\u516c\u53f8", "\u76f4\u64ad", "\u611f\u60c5", "\u5206\u624b")):
            importance += 1
        if len(text) > 100:
            importance += 1
        age_days = max(0, (time.time() - float(row.get("epoch", time.time()))) / 86400)
        recency = max(0, 2 - age_days / 14)
        rows.append((overlap * 4 + importance + recency, float(row.get("epoch", 0)), row))
    rows.sort(key=lambda x: (x[0], x[1]), reverse=True)
    recent_ids = {id(r) for _, _, r in sorted(rows, key=lambda x: x[1], reverse=True)[:2]}
    selected = []
    for score, _, row in rows:
        if score > 0.5 or id(row) in recent_ids:
            selected.append(row)
        if len(selected) >= limit:
            break
    return selected


def append_memory_event(
    user_text: str,
    assistant_text: str,
    events_path: Path | None = None,
    contact: str = DEFAULT_CONTACT,
    *,
    event_id: str | None = None,
    source: str = "wechat",
    metadata: dict | None = None,
) -> dict:
    path = Path(events_path) if events_path else PATHS.memory_events
    event_id = str(event_id or uuid.uuid4().hex)
    row = {
        "event_id": event_id,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": time.time(),
        "contact": contact,
        "source": source,
        "user": user_text,
        "assistant": assistant_text,
        "metadata": metadata or {},
    }
    with _store(path) as store:
        inserted = store.add_event(
            event_id,
            contact,
            source,
            user_text,
            assistant_text,
            timestamp=row["time"],
            epoch=row["epoch"],
            importance=1 if metadata else 0,
            metadata=metadata,
        )
        if inserted:
            append_jsonl(path, row)
            return row
        return store.get_event(event_id) or row


def get_memory_event(event_id: str, events_path: Path | None = None) -> dict | None:
    path = Path(events_path) if events_path else PATHS.memory_events
    with _store(path) as store:
        return store.get_event(event_id)
