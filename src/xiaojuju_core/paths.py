from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class Paths:
    root: Path
    persona: Path
    state: Path
    memory_events: Path
    goals: Path
    daily_plans: Path
    activities: Path
    output: Path
    reflection: Path
    audit: Path
    paused: Path

    @classmethod
    def production(cls):
        root = Path(r"D:\yige-personal-kb")
        persona = root / "12_社交代理" / "小居居"
        auto = persona / "自主生活"
        return cls(
            root=root,
            persona=persona,
            state=persona / "状态" / "当前状态.json",
            memory_events=persona / "记忆" / "事件.jsonl",
            goals=auto / "目标" / "目标队列.json",
            daily_plans=auto / "每日计划",
            activities=auto / "活动日志",
            output=auto / "活动成果",
            reflection=auto / "反思",
            audit=persona / "行为日志" / "自主内核.jsonl",
            paused=auto / "paused.flag",
        )