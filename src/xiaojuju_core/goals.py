import time
from pathlib import Path
from .paths import Paths
from .storage import atomic_write_json, read_json

PATHS = Paths.production()

def _load(path):
    data = read_json(path, {"version": 1, "goals": []})
    if not isinstance(data, dict) or not isinstance(data.get("goals"), list):
        return {"version": 1, "goals": []}
    return data

def add_goal(title: str, source: str, priority: int, detail: str = "", permission: str = "internal", goals_path: Path | None = None) -> dict:
    path = Path(goals_path) if goals_path else PATHS.goals
    data = _load(path)
    goal = {
        "id": str(time.time_ns()),
        "created_epoch": time.time(),
        "source": source,
        "priority": int(priority),
        "title": title,
        "detail": detail,
        "status": "queued",
        "permission": permission,
        "result": "",
    }
    data["goals"].append(goal)
    atomic_write_json(path, data)
    return goal

def next_goal(goals_path: Path | None = None) -> dict | None:
    path = Path(goals_path) if goals_path else PATHS.goals
    goals = [g for g in _load(path)["goals"] if g.get("status") in {"queued", "failed"}]
    if not goals:
        return None
    goals.sort(key=lambda g: (0 if g.get("source") == "boss" else 1, -int(g.get("priority", 0)), float(g.get("created_epoch", 0))))
    return goals[0]

def set_goal_status(goal_id: str, status: str, result: str = "", goals_path: Path | None = None) -> dict:
    path = Path(goals_path) if goals_path else PATHS.goals
    data = _load(path)
    for goal in data["goals"]:
        if goal.get("id") == goal_id:
            goal["status"] = status
            goal["result"] = result
            goal["updated_epoch"] = time.time()
            atomic_write_json(path, data)
            return goal
    raise KeyError(goal_id)