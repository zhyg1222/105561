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

    @property
    def memory_db(self) -> Path:
        return self.persona / "\u8bb0\u5fc6" / "\u8bb0\u5fc6.db"

    @property
    def event_bus(self) -> Path:
        return self.persona / "\u4e8b\u4ef6\u603b\u7ebf" / "\u4e8b\u4ef6.db"

    @classmethod
    def production(cls):
        from .config import load_config
        cfg = load_config()
        root = Path(r"D:\yige-personal-kb")
        persona = Path(cfg["runtime"]["data_root"])
        auto = persona / "\u81ea\u4e3b\u751f\u6d3b"
        return cls(
            root=root,
            persona=persona,
            state=persona / "\u72b6\u6001" / "\u5f53\u524d\u72b6\u6001.json",
            memory_events=persona / "\u8bb0\u5fc6" / "\u4e8b\u4ef6.jsonl",
            goals=auto / "\u76ee\u6807" / "\u76ee\u6807\u961f\u5217.json",
            daily_plans=auto / "\u6bcf\u65e5\u8ba1\u5212",
            activities=auto / "\u6d3b\u52a8\u65e5\u5fd7",
            output=auto / "\u6d3b\u52a8\u6210\u679c",
            reflection=auto / "\u53cd\u601d",
            audit=persona / "\u884c\u4e3a\u65e5\u5fd7" / "\u81ea\u4e3b\u5185\u6838.jsonl",
            paused=auto / "paused.flag",
        )
