from pathlib import Path
from .paths import Paths
from .state import load_life_state
from .storage import atomic_write_json, read_json

PATHS = Paths.production()

def ensure_daily_plan(day: str, plans_dir: Path | None = None) -> dict:
    directory = Path(plans_dir) if plans_dir else PATHS.daily_plans
    path = directory / f"{day}.json"
    existing = read_json(path, None)
    if isinstance(existing, dict):
        return existing
    state = load_life_state()
    plan = {
        "date": day,
        "energy": int(state.get("energy", 72)),
        "social_battery": int(state.get("social_battery", 80)),
        "items": [
            {"id":"morning-review","time":"08:00","title":"整理今日状态与目标","status":"queued"},
            {"id":"focus-block","time":"09:00","title":"研究、创作或处理老大任务","status":"queued"},
            {"id":"social-block","time":"15:00","title":"查看授权社交机会","status":"queued"},
            {"id":"live-prep","time":"17:00","title":"准备直播或公开表达内容","status":"queued"},
            {"id":"reflection","time":"22:00","title":"记录真实活动和反思","status":"queued"},
        ],
    }
    atomic_write_json(path, plan)
    return plan

def mark_plan_item(day: str, item_id: str, status: str, plans_dir: Path | None = None) -> dict:
    directory = Path(plans_dir) if plans_dir else PATHS.daily_plans
    path = directory / f"{day}.json"
    plan = read_json(path, None)
    if not isinstance(plan, dict):
        plan = ensure_daily_plan(day, directory)
    for item in plan.get("items", []):
        if item.get("id") == item_id:
            item["status"] = status
            atomic_write_json(path, plan)
            return plan
    raise KeyError(item_id)