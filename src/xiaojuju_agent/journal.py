from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

EXCLUDED_PREFIXES = (
    "eval:",
    "approval-",
    "browser-read-",
    "graphiti-live",
    "agent-client-test",
    "unicode-header-test",
    "integration-",
    "tool-",
    "fetch-integration",
    "queue-",
    "bridge-",
    "health:",
)

EXCLUDED_MESSAGE_PREFIXES = ("bridge-", "health:")
TEST_TEXT_MARKERS = (
    "persistent memory queue",
    "memory queue acceptance",
    "introduce yourself",
    "say hi in one short sentence",
    "微信桥",
    "跨进程测试",
)


def should_include_event(event_id: str) -> bool:
    value = str(event_id)
    return not any(value.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


def should_include_message(message_id: str) -> bool:
    return not any(str(message_id).startswith(prefix) for prefix in EXCLUDED_MESSAGE_PREFIXES)


def meaningful_text(value: Any) -> bool:
    text = str(value or "").strip().lower()
    if not text or not any(char not in "?？!！.。,， " for char in text):
        return False
    return not any(marker.lower() in text for marker in TEST_TEXT_MARKERS)


def _clip(value: Any, limit: int = 800) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def render_journal(
    *,
    day: str,
    events: list[dict[str, Any]],
    outbox: list[dict[str, Any]],
    activities: list[dict[str, Any]],
    health: dict[str, Any] | None,
    memory_stats: dict[str, Any] | None,
    reflection_text: str = "",
) -> str:
    included_events = [
        row
        for row in events
        if should_include_event(str(row.get("event_id", "")))
        and meaningful_text(row.get("user_text"))
    ]
    done_activities = [row for row in activities if row.get("status") == "done"]
    failed_activities = [row for row in activities if row.get("status") not in {None, "done"}]
    visible_outbox = [
        row for row in outbox if should_include_message(str(row.get("message_id", "")))
    ]
    sent_messages = [row for row in visible_outbox if row.get("status") == "sent"]

    lines = [
        f"# {day} 小居居日录",
        "",
        "> 自动生成，只记录真实发生的事件；没有记录的部分不补写。",
        "",
        "## 今日概览",
        "",
        f"- 真实对话事件：{len(included_events)}",
        f"- 完成的自主活动：{len(done_activities)}",
        f"- 自主活动失败/暂停：{len(failed_activities)}",
        f"- 已发送外部消息：{len(sent_messages)}",
        f"- 记忆队列：{json.dumps(memory_stats or {}, ensure_ascii=False)}",
    ]
    if health:
        lines.append(f"- 健康检查：{'正常' if health.get('ok') else '异常'}")

    lines += ["", "## 今日对话与决策", ""]
    if not included_events:
        lines.append("- 暂无真实对话记录。")
    for row in included_events:
        lines += [
            f"### {_clip(row.get('created_at', ''), 40)} · {row.get('source', '')}/{_clip(row.get('contact_id', 'owner'), 80)}",
            "",
            f"- 老大：{_clip(row.get('user_text'))}",
            f"- 小居居：{_clip(row.get('reply'))}",
            "",
        ]

    lines += ["## 自主生活", ""]
    if not activities:
        lines.append("- 今天没有自主活动记录。")
    for row in activities:
        status = str(row.get("status", "unknown"))
        marker = "完成" if status == "done" else "未完成"
        detail = row.get("result_path") or row.get("error") or ""
        lines.append(
            f"- {row.get('time', '')} · {_clip(row.get('goal', ''))} · {marker}"
            + (f" · {_clip(detail, 300)}" if detail else "")
        )

    lines += ["", "## 对外发送", ""]
    if not visible_outbox:
        lines.append("- 今天没有对外发送记录。")
    for row in visible_outbox:
        lines.append(
            f"- {row.get('created_at', '')} · {row.get('contact_id', '')} · "
            f"{row.get('status', '')} · {_clip(row.get('text'), 300)}"
        )

    lines += ["", "## 记忆与健康", ""]
    if health:
        checks = health.get("checks", {})
        bad = [name for name, item in checks.items() if isinstance(item, dict) and not item.get("ok")]
        lines.append(f"- 健康总状态：{'正常' if health.get('ok') else '异常'}")
        lines.append(f"- 异常检查：{', '.join(bad) if bad else '无'}")
    else:
        lines.append("- 今日没有健康检查快照。")
    lines += ["", "## 今日反思", "", reflection_text.strip() or "待补充：今天的行为是否偏离了目标？有没有重复犯错？"]

    lines += ["", "## 明日起点", ""]
    if failed_activities:
        lines.append(f"- 先复核未完成活动：{_clip(failed_activities[0].get('goal', ''))}")
    elif included_events:
        lines.append("- 从今天真实未解决的问题继续，不凭假设制造新任务。")
    else:
        lines.append("- 等老大补充真实经历后，再生成具体建议；不编造今天发生了什么。")
    lines.append("")
    return "\n".join(lines)


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line in lines:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def safe_day(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("day must use YYYY-MM-DD")
    datetime.strptime(value, "%Y-%m-%d")
    return value