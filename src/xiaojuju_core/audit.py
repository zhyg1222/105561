import time
from pathlib import Path
from .paths import Paths
from .storage import append_jsonl

PATHS = Paths.production()

def audit_event(actor: str, action: str, target: str, result: str, audit_path: Path | None = None) -> None:
    path = Path(audit_path) if audit_path else PATHS.audit
    append_jsonl(path, {
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "actor": actor,
        "action": action,
        "target": target,
        "result": result,
    })