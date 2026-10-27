import json, time
from datetime import datetime, time as dtime
from pathlib import Path
from .activity import run_activity
from .audit import audit_event
from .config import load_config
from .daily_plan import ensure_daily_plan
from .event_bus import EventBus
from .goals import add_goal, next_goal, set_goal_status
from .curiosity import add_interest, next_interest, mark_interest
from .memory import append_memory_event
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


def _clock(value: str) -> dtime:
    hour, minute = str(value).split(":", 1)
    return dtime(int(hour), int(minute))


def _apply_result(paths, goal: dict, result: dict, now: datetime, bus_event_id: str) -> None:
    activity_path = paths.activities / f"{now.strftime('%Y-%m-%d')}.jsonl"
    interest_path = (
        paths.persona
        / "\u81ea\u4e3b\u751f\u6d3b"
        / "\u5174\u8da3"
        / "\u5173\u6ce8\u961f\u5217.json"
    )
    if result.get("status") == "done":
        set_goal_status(goal["id"], "done", result.get("path", ""), paths.goals)
        if goal.get("interest_id"):
            mark_interest(goal["interest_id"], "done", result.get("path", ""), interest_path)
        if result.get("follow_up"):
            add_interest(
                result["follow_up"],
                "\u7531\u4e0a\u6b21\u81ea\u4e3b\u7814\u7a76\u4ea7\u751f",
                interests_path=interest_path,
            )
        try:
            append_memory_event(
                goal.get("title", "\u81ea\u4e3b\u6d3b\u52a8"),
                f"\u5b8c\u6210\uff0c\u6210\u679c\u5b58\u653e\u5728\uff1a{result.get('path', '')}",
                events_path=paths.memory_events,
                contact="\u81ea\u5df1",
                event_id="research-memory:" + bus_event_id,
                source="research",
                metadata={"goal_id": goal.get("id"), "result_path": result.get("path", "")},
            )
        except Exception:
            pass
    else:
        set_goal_status(goal["id"], "failed", result.get("error", "failed"), paths.goals)
        if goal.get("interest_id"):
            mark_interest(
                goal["interest_id"], "failed", result.get("error", "failed"), interest_path
            )
    existed = any(row.get("bus_event_id") == bus_event_id for row in _activity_rows(activity_path))
    if not existed:
        row = {
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "epoch": now.timestamp(),
            "bus_event_id": bus_event_id,
            "goal_id": goal.get("id"),
            "goal": goal.get("title", ""),
            "status": result.get("status"),
            "result_path": result.get("path", ""),
            "error": result.get("error", ""),
        }
        append_jsonl(activity_path, row)
    audit_event(
        "\u5c0f\u5c45\u5c45",
        "research",
        goal.get("title", ""),
        result.get("status", ""),
        paths.audit,
    )
    if now.time() >= dtime(22, 0):
        write_daily_reflection(now.strftime("%Y-%m-%d"), activity_path, paths.reflection)


def tick(
    paths,
    now: datetime,
    runner=None,
    dry_run: bool = False,
    config: dict | None = None,
    force: bool = False,
) -> dict:
    cfg = config or load_config()
    auto = cfg["autonomy"]
    quiet_start, quiet_end = (_clock(x) for x in auto["quiet_hours"])
    daily_limit = int(auto["activity_limit_per_day"])
    min_gap_seconds = int(auto["activity_gap_minutes"]) * 60
    if paths.paused.exists():
        return {"status": "paused"}
    if quiet_start <= now.time() < quiet_end:
        return {"status": "quiet_hours"}
    ensure_daily_plan(now.strftime("%Y-%m-%d"), paths.daily_plans)
    activity_path = paths.activities / f"{now.strftime('%Y-%m-%d')}.jsonl"
    rows = _activity_rows(activity_path)
    if now.time() >= dtime(22, 0):
        write_daily_reflection(now.strftime("%Y-%m-%d"), activity_path, paths.reflection)
    if not force and sum(1 for r in rows if r.get("status") == "done") >= daily_limit:
        return {"status": "daily_limit"}
    epochs = [float(r.get("epoch", 0)) for r in rows if r.get("epoch")]
    if not force and epochs and now.timestamp() - max(epochs) < min_gap_seconds:
        return {"status": "activity_gap"}
    goal = next_goal(paths.goals)
    if not goal and not auto.get("allow_self_goals", True):
        return {"status": "no_goal"}
    if not goal:
        interest_path = (
            paths.persona
            / "\u81ea\u4e3b\u751f\u6d3b"
            / "\u5174\u8da3"
            / "\u5173\u6ce8\u961f\u5217.json"
        )
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
    action = (
        "research" if goal.get("permission") == "internal" else goal.get("permission", "research")
    )
    decision, reason = check_permission(action, goal.get("source", "self"))
    if decision != "allow":
        audit_event("\u5c0f\u5c45\u5c45", action, goal.get("title", ""), decision, paths.audit)
        return {"status": "permission_blocked", "decision": decision, "reason": reason}
    if dry_run:
        return {"status": "dry_run", "goal": goal}

    bus_event_id = "autonomy:" + str(goal["id"])
    with EventBus(paths.event_bus) as bus:
        existing = bus.get(bus_event_id)
        cached_result = {}
        if existing and existing.get("status") == "completed":
            saved = existing.get("result") or {}
            if isinstance(saved, dict) and isinstance(saved.get("result"), dict):
                cached_result = saved["result"]
            if cached_result.get("status") == "done":
                _apply_result(paths, goal, cached_result, now, bus_event_id)
                return {
                    "status": "done",
                    "goal": goal.get("title", ""),
                    "result": cached_result,
                    "recovered": True,
                }
            # A failed/stale cached result must not block future autonomy ticks.
            bus_event_id = f"{bus_event_id}:retry:{int(time.time())}"
        bus.enqueue(
            bus_event_id,
            "autonomy.task",
            {"goal": goal, "scheduled_for": now.strftime("%Y-%m-%d %H:%M:%S")},
            priority=20,
        )
        existing = bus.get(bus_event_id)
        claimed = bus.claim(bus_event_id)
        if claimed is None:
            return {
                "status": "bus_busy",
                "goal": goal.get("title", ""),
                "bus_status": (existing or {}).get("status"),
            }
        state = load_life_state(paths.state)
        try:
            result = run_activity(
                goal, state, now.strftime("%Y-%m-%d %H:%M:%S"), runner, paths.output
            )
        except Exception as exc:
            result = {"status": "failed", "error": repr(exc)}
        package = {"status": result.get("status"), "goal": goal.get("title", ""), "result": result}
        bus.complete(bus_event_id, package)
        _apply_result(paths, goal, result, now, bus_event_id)
        return {"status": result.get("status"), "goal": goal.get("title", ""), "result": result}
