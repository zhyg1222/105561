import json, time
from datetime import datetime, time as dtime
from pathlib import Path
from .activity import run_activity
from .audit import audit_event
from .daily_plan import ensure_daily_plan
from .goals import add_goal, next_goal, set_goal_status
from .curiosity import add_interest, next_interest, mark_interest
from .permissions import check_permission
from .reflection import write_daily_reflection
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
    if now.time() >= dtime(22, 0):
        write_daily_reflection(now.strftime("%Y-%m-%d"), activity_path, paths.reflection)
    if sum(1 for r in rows if r.get("status") == "done") >= DAILY_LIMIT:
        return {"status": "daily_limit"}
    epochs = [float(r.get("epoch", 0)) for r in rows if r.get("epoch")]
    if epochs and now.timestamp() - max(epochs) < MIN_GAP_SECONDS:
        return {"status": "activity_gap"}
    goal = next_goal(paths.goals)
    if not goal:
        interest_path = paths.persona / "\u81ea\u4e3b\u751f\u6d3b" / "\u5174\u8da3" / "\u5173\u6ce8\u961f\u5217.json"
        interest = next_interest(interest_path)
        if interest:
            title = "\u7814\u7a76\uff1a" + interest.get("topic", "\u81ea\u4e3b\u4e3b\u9898")
            detail = interest.get("reason", "")
            interest_id = interest.get("id", "")
        else:
            title = "\u81ea\u4e3b\u5b89\u6392\u4e00\u6b21\u6d3b\u52a8"
            detail = "\u6839\u636e\u5f53\u524d\u5174\u8da3\u548c\u72b6\u6001\uff0c\u81ea\u4e3b\u9009\u62e9\u4e00\u6b21\u5b89\u5168\u7684\u7814\u7a76\u3001\u5199\u4f5c\u6216\u76f4\u64ad\u51c6\u5907\u6d3b\u52a8\u3002"
            interest_id = ""
        add_goal(title, "self", 10, detail=detail, goals_path=paths.goals, interest_id=interest_id)
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
        interest_path = paths.persona / "自主生活" / "兴趣" / "关注队列.json"
        if goal.get("interest_id"):
            mark_interest(goal["interest_id"], "done", result.get("path", ""), interest_path)
        if result.get("follow_up"):
            add_interest(result["follow_up"], "由上次自主研究产生", interests_path=interest_path)
    else:
        set_goal_status(goal["id"], "failed", result.get("error", "failed"), paths.goals)
        if goal.get("interest_id"):
            mark_interest(goal["interest_id"], "failed", result.get("error", "failed"), paths.persona / "自主生活" / "兴趣" / "关注队列.json")
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
    if now.time() >= dtime(22, 0):
        write_daily_reflection(now.strftime("%Y-%m-%d"), activity_path, paths.reflection)
    return {"status": result.get("status"), "goal": goal.get("title", ""), "result": result}