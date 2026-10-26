import time, uuid
from pathlib import Path
from .paths import Paths
from .storage import atomic_write_json, read_json

PATHS = Paths.production()
QUEUE = PATHS.persona / "自主生活" / "兴趣" / "关注队列.json"

def _load(path):
    data=read_json(path,{"version":1,"interests":[]})
    if not isinstance(data,dict) or not isinstance(data.get("interests"),list):
        return {"version":1,"interests":[]}
    return data

def add_interest(topic: str, reason: str, interests_path: Path | None = None) -> dict:
    topic=topic.strip(); reason=reason.strip()
    if not topic:
        raise ValueError("topic is required")
    path=Path(interests_path) if interests_path else QUEUE
    data=_load(path)
    for existing in data["interests"]:
        if existing.get("topic") == topic and existing.get("status") in {"queued", "doing"}:
            return existing
    item={"id":uuid.uuid4().hex,"topic":topic,"reason":reason,"status":"queued","created_epoch":time.time(),"note":""}
    data["interests"].append(item); atomic_write_json(path,data); return item

def next_interest(interests_path: Path | None = None) -> dict | None:
    path=Path(interests_path) if interests_path else QUEUE
    for item in _load(path)["interests"]:
        if item.get("status")=="queued": return item
    return None

def mark_interest(interest_id: str, status: str, note: str = "", interests_path: Path | None = None) -> dict:
    path=Path(interests_path) if interests_path else QUEUE
    data=_load(path)
    for item in data["interests"]:
        if item.get("id")==interest_id:
            item["status"]=status; item["note"]=note; item["updated_epoch"]=time.time()
            atomic_write_json(path,data); return item
    raise KeyError(interest_id)