import json, time
from datetime import datetime, time as dtime
from pathlib import Path
from .activity import run_activity
from .audit import audit_event
from .daily_plan import ensure_daily_plan
from .goals import next_goal, set_goal_status
from .permissions import check_permission
from .state import load_life_state
from .storage import append_jsonl

QUIET_START = dtime(0, 0)
QUIET_END = dtime(7, 30)
DAILY_LIMIT = 4
MIN_GAP_SECONDS = 120 * 60

def _activity_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    return rows

def tick(paths, now: datetime, runner=None, dry_run: bool = False) -> dict:
    if paths.paused.exists():
        return {"status": "paused"}
    if QUIET_START <= now.time() < QUIET_END:
        return {"status": "quiet_hours"}
    ensure_daily_plan(now.strftime("%Y-%m-%d"), paths.daily_plans)
    activity_path = paths.activities / f"{now.strftime('%Y-%m-%d')}.jsonl"
    rows = _activity_rows(activity_path)
    if sum(1 for r in rows if r.get("status") == "done") >= DAILY_LIMIT:
        return {"status": "daily_limit"}
    epochs = [float(r.get("epoch", 0)) for r in rows if r.get("epoch")]
    if epochs and now.timestamp() - max(epochs) < MIN_GAP_SECONDS:
        return {"status": "activity_gap"}
    goal = next_goal(paths.goals)
    if not goal:
        return {"status": "no_goal"}
    action = "research" if goal.get("permission") == "internal" else goal.get("permission", "research")
    decision, reason = check_permission(action, goal.get("source", "self"))
    if decision != "allow":
        audit_event("小居居", action, goal.get("title", ""), decision, paths.audit)
        return {"status": "permission_blocked", "decision": decision, "reason": reason}
    if dry_run:
        return {"status": "dry_run", "goal": goal}
    state = load_life_state(paths.state)
    result = run_activity(goal, state, now.strftime("%Y-%m-%d %H:%M:%S"), runner, paths.output)
    if result.get("status") == "done":
        set_goal_status(goal["id"], "done", result.get("path", ""), paths.goals)
    else:
        set_goal_status(goal["id"], "failed", result.get("error", "failed"), paths.goals)
    row = {
        "time": now.strftime("%Y-%m-%d %H:%M:%S"),
        "epoch": now.timestamp(),
        "goal_id": goal.get("id"),
        "goal": goal.get("title", ""),
        "status": result.get("status"),
        "result_path": result.get("path", ""),
        "error": result.get("error", ""),
    }
    append_jsonl(activity_path, row)
    audit_event("小居居", action, goal.get("title", ""), result.get("status", ""), paths.audit)
    return {"status": result.get("status"), "goal": goal.get("title", ""), "result": result}