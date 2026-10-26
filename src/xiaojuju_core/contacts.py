import hashlib
from pathlib import Path
from .storage import read_json

DEFAULT_CONTACTS = Path(r"D:\yige-personal-kb\12_社交代理\小居居\社交\微信联系人.json")

def contact_key(name: str) -> str:
    return hashlib.sha1(str(name).encode("utf-8")).hexdigest()[:20]

def load_wechat_contacts(path: Path | None = None) -> list[dict]:
    p=Path(path) if path else DEFAULT_CONTACTS
    data=read_json(p,{"version":1,"contacts":[]})
    rows=data.get("contacts",[]) if isinstance(data,dict) else []
    result=[]
    for row in rows:
        if not isinstance(row,dict): continue
        name=str(row.get("name","")).strip()
        if name and row.get("enabled",True):
            result.append({**row,"name":name})
    return result