import time, uuid
from pathlib import Path
from .paths import Paths
from .storage import atomic_write_json, read_json

PATHS=Paths.production()
OUTBOX=PATHS.persona/"社交"/"待发送.json"

def _load(path):
    data=read_json(path,{"version":1,"messages":[]})
    if not isinstance(data,dict) or not isinstance(data.get("messages"),list):
        return {"version":1,"messages":[]}
    return data

def enqueue_message(contact: str, text: str, kind: str = "message", outbox_path: Path | None = None) -> dict:
    contact=str(contact).strip(); text=str(text).strip()
    if not contact or not text:
        raise ValueError("contact and text are required")
    path=Path(outbox_path) if outbox_path else OUTBOX
    data=_load(path)
    item={"id":uuid.uuid4().hex,"contact":contact,"text":text,"kind":kind,"status":"queued","attempts":0,"created_epoch":time.time(),"last_error":""}
    data["messages"].append(item); atomic_write_json(path,data); return item

def pending_messages(outbox_path: Path | None = None, contact: str | None = None) -> list[dict]:
    path=Path(outbox_path) if outbox_path else OUTBOX
    rows=[]
    for msg in _load(path)["messages"]:
        if msg.get("status")!="queued" or int(msg.get("attempts",0))>=3: continue
        if contact and msg.get("contact")!=contact: continue
        rows.append(msg)
    return rows

def mark_message(message_id: str, status: str, error: str = "", outbox_path: Path | None = None) -> dict:
    path=Path(outbox_path) if outbox_path else OUTBOX
    data=_load(path)
    for msg in data["messages"]:
        if msg.get("id")==message_id:
            msg["status"]=status; msg["last_error"]=error; msg["updated_epoch"]=time.time()
            if status!="sent": msg["attempts"]=int(msg.get("attempts",0))+1
            atomic_write_json(path,data); return msg
    raise KeyError(message_id)