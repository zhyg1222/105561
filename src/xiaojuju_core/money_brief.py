import json, re
from pathlib import Path
from .paths import Paths

PATHS = Paths.production()


def _fallback(rows, next_topics):
    lines = ["今日赚钱研究简报"]
    done = [r for r in rows if r.get("status") == "done"]
    if done:
        for row in done[:3]:
            lines.append(f'- 今天研究：{row.get("goal", "")}')
    else:
        lines.append('- 今天还没有完成的赚钱研究。')
    if next_topics:
        lines.append(f'- 下一步：{next_topics[0].get("topic", "")}')
    return "\n".join(lines)[:450]


def build_brief_text(rows: list[dict], next_topics: list[dict], model_fn=None) -> str:
    evidence = []
    for row in rows[:6]:
        item = {
            "goal": row.get("goal", ""),
            "status": row.get("status", ""),
            "result_path": row.get("result_path", ""),
        }
        path = Path(str(row.get("result_path", "")))
        if path.exists() and path.is_file():
            item["excerpt"] = path.read_text(encoding="utf-8", errors="replace")[:700]
        evidence.append(item)
    if model_fn:
        system = (
            "你是小居居。只输出4行纯文本发微信：\n"
            "第1行：今天真实研究了什么；\n"
            "第2行：机会和证据；\n"
            "第3行：最小验证动作；\n"
            "第4行：风险和明天准备继续查什么。\n"
            "每行不超过80个汉字，总共不超过320个汉字。只使用真实记录，不编造；没有外部证据就说这是待验证假设。"
            "不要标题、列表、Markdown、emoji、投资建议或收益承诺。"
        )
        user = json.dumps({
            "today": evidence,
            "next_topics": [x.get("topic", "") for x in next_topics[:3]],
        }, ensure_ascii=False)
        try:
            try:
                text = str(model_fn(system, user, max_tokens=120)).strip()
            except TypeError:
                text = str(model_fn(system, user)).strip()
            if text:
                text = re.sub(r"[#*`>]+", "", text)
                lines = [re.sub(r"\s+", " ", x).strip(" -\t") for x in text.splitlines() if x.strip()]
                text = "\n".join(lines[:4]).strip()
                if len(text) > 360:
                    cutoff = max(text.rfind(x, 0, 360) for x in "。！？\n")
                    text = text[:cutoff + 1] if cutoff > 160 else text[:360]
                return text.strip()
        except Exception:
            pass
    return _fallback(rows, next_topics)


def save_brief(day: str, text: str, brief_dir: Path | None = None) -> Path:
    directory = Path(brief_dir) if brief_dir else PATHS.persona / "日报" / "赚钱研究"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{day}.md"
    path.write_text(text.strip() + "\n", encoding="utf-8")
    return path