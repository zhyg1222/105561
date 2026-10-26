import json
from pathlib import Path

def write_daily_reflection(day: str, activity_path: Path, reflection_dir: Path) -> Path | None:
    if not activity_path.exists():
        return None
    rows = []
    for line in activity_path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    if not rows:
        return None
    done = [r for r in rows if r.get("status") == "done"]
    failed = [r for r in rows if r.get("status") != "done"]
    lines = [f"# {day} 自主反思", "", "## 今天真实完成的活动", ""]
    if done:
        for row in done:
            lines.append(f'- {row.get("time", "")}：{row.get("goal", "")}（{row.get("result_path", "")}）')
    else:
        lines.append("- 今天没有完成的活动。")
    lines += ["", "## 未完成或失败", ""]
    if failed:
        for row in failed:
            lines.append(f'- {row.get("time", "")}：{row.get("goal", "")} — {row.get("error", "失败")}')
    else:
        lines.append("- 无。")
    pending = [r for r in failed if r.get("goal")]
    lines += ["", "## 明天的起点", ""]
    if pending:
        lines.append(f'- 先检查未完成目标：{pending[0].get("goal", "")}')
    else:
        lines.append("- 根据状态和兴趣继续自主安排，不为了忙碌而制造活动。")
    lines.append("")
    reflection_dir.mkdir(parents=True, exist_ok=True)
    path = reflection_dir / f"{day}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path