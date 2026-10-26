import time
from pathlib import Path
from .paths import Paths
from .storage import atomic_write_json, read_json

PATHS = Paths.production()

def load_life_state(state_path: Path | None = None) -> dict:
    path = Path(state_path) if state_path else PATHS.state
    return read_json(path, {
        "updated_epoch": time.time(), "day": time.strftime("%Y-%m-%d"),
        "energy": 72, "social_battery": 80, "mood": "松弛",
        "focus": "", "interactions_today": 0,
    })

def update_life_state(incoming: str, state_path: Path | None = None, now: float | None = None) -> dict:
    path = Path(state_path) if state_path else PATHS.state
    now = time.time() if now is None else now
    state = load_life_state(path)
    today = time.strftime("%Y-%m-%d", time.localtime(now))
    if state.get("day") != today:
        state["day"] = today
        state["energy"] = 72
        state["social_battery"] = 80
        state["interactions_today"] = 0
    elapsed_h = max(0, now - float(state.get("updated_epoch", now))) / 3600
    state["energy"] = min(85, int(state.get("energy", 72) + elapsed_h * 2))
    state["social_battery"] = min(90, int(state.get("social_battery", 80) + elapsed_h * 3))
    text = str(incoming)
    if any(k in text for k in ("累", "困", "难受", "烦", "焦虑")):
        state["mood"] = "收着劲，先听你说"
    elif any(k in text for k in ("项目", "创业", "工作", "赚钱", "瞳云", "艾瑞斯")):
        state["mood"] = "认真"
    elif any(k in text for k in ("游戏", "玩", "吃", "视频", "直播", "有意思")):
        state["mood"] = "来劲"
    else:
        state["mood"] = "松弛"
    state["focus"] = text[:40]
    state["interactions_today"] = int(state.get("interactions_today", 0)) + 1
    state["energy"] = max(25, int(state["energy"]) - 1)
    state["social_battery"] = max(20, int(state["social_battery"]) - 2)
    state["updated_epoch"] = now
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now))
    atomic_write_json(path, state)
    return state