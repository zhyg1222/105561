import json, os, re, subprocess, time
from datetime import datetime
from pathlib import Path
from .paths import Paths
from .audit import audit_event

PATHS = Paths.production()
NODE = Path(r"D:\Program Files\nodejs\node.exe")
DSH_BIN = Path(
    r"D:\yige-personal-kb\.runtime\dsh-personal\node_modules\@deepseek-ai\dsh\lib\bin.js"
)


def audit_web_events(stdout: str, audit_path: Path | None = None) -> None:
    if audit_path is None:
        audit_path = (
            PATHS.persona
            / "\u884c\u4e3a\u65e5\u5fd7"
            / "\u8054\u7f51"
            / (time.strftime("%Y-%m-%d") + ".jsonl")
        )
    pending = {}
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "tool_call" and event.get("tool") in {"web_search", "web_fetch"}:
            pending[event.get("callId", "")] = event.get("tool")
            audit_event(
                "XiaoJuJu",
                event.get("tool"),
                json.dumps(event.get("input"), ensure_ascii=False),
                "started",
                audit_path,
            )
        elif event.get("type") == "tool_result" and event.get("callId") in pending:
            audit_event(
                "XiaoJuJu",
                pending.pop(event.get("callId")),
                "",
                event.get("status", ""),
                audit_path,
            )


def _safe_title(title: str) -> str:
    value = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9-]+", "-", title).strip("-")[:40]
    return value or "activity"


def _parse_final(stdout: str) -> dict:
    final = ""
    for line in (stdout or "").splitlines():
        try:
            event = json.loads(line)
        except Exception:
            continue
        if event.get("type") == "final":
            final = str(event.get("text", "")) or final
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", final.strip(), flags=re.I)
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def default_runner(prompt: str) -> dict:
    env = os.environ.copy()
    env["DSH_HOME"] = r"D:\yige-personal-kb\.runtime\dsh-personal\home"
    env["DSH_TELEMETRY_DISABLED"] = "1"
    env["DSH_TELEMETRY_MODE"] = "DISABLED"
    env["DSH_PERMISSION_MODE"] = "read-only"
    env["PYTHONUTF8"] = "1"
    for _ in range(2):
        try:
            result = subprocess.run(
                [str(NODE), str(DSH_BIN), "--profile", "xiaojuju", "headless", "--json", prompt],
                env=env,
                cwd=str(PATHS.persona),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
            audit_web_events(result.stdout)
            if result.returncode == 0:
                parsed = _parse_final(result.stdout)
                if parsed:
                    return parsed
        except Exception:
            pass
        time.sleep(1)
    return {}


def _build_prompt(goal: dict, state: dict, now: str) -> str:
    return f"""你是小居居，一个独立的 AI 互联网智能体。现在是 {now}。
当前状态：{json.dumps(state, ensure_ascii=False)}
当前目标来源：{goal.get("source", "self")}
目标标题：{goal.get("title", "自由安排")}
目标详情：{goal.get("detail", "")}

当前目标是本次活动的唯一任务。除非目标标题明确是“自主安排一次活动”，必须围绕目标标题和详情展开，不得换成无关主题；标题和正文必须体现目标中的关键词。
请自主完成一次安全、可验证的内部活动，例如公开网页研究、写一段观察或整理一个想法。
只允许公开网页搜索/读取和内部写作，不得发消息、发帖、登录、上传、花钱或修改账号。
如果使用了网页信息，必须保留来源 URL。没有查到就如实说明。
只输出 JSON，不要 Markdown 代码围栏：
{{"title":"成果标题","markdown":"实际成果正文，包含来源（如有）","follow_up":"下一个你自己真想继续调查的问题"}}
"""


def _goal_terms(goal: dict) -> list[str]:
    raw = str(goal.get("title", "")) + str(goal.get("detail", ""))
    if "自主安排一次活动" in raw or "自由研究" in raw:
        return []
    chars = re.findall(r"[\u4e00-\u9fff]", raw)
    terms = {"".join(chars[i : i + 2]) for i in range(max(0, len(chars) - 1))}
    stop = {"研究", "目标", "当前", "本次", "一个", "一次", "如何", "可以", "进行", "相关", "内容", "无关"}
    return sorted(term for term in terms if term not in stop)


def _goal_aligned(goal: dict, title: str, markdown: str) -> bool:
    terms = _goal_terms(goal)
    if not terms:
        return True
    text = str(title) + "\n" + str(markdown)
    return any(term in text for term in terms)


def run_activity(
    goal: dict, state: dict, now: str, runner=None, output_dir: Path | None = None
) -> dict:
    runner = runner or default_runner
    output = Path(output_dir) if output_dir else PATHS.output
    prompt = _build_prompt(goal, state, now)
    result = {}
    last_error = "empty runner output"
    for attempt in range(2):
        try:
            candidate = runner(prompt)
        except Exception as exc:
            last_error = repr(exc)
            candidate = {}
        if not isinstance(candidate, dict):
            candidate = {}
        title = str(candidate.get("title", "")).strip()
        markdown = str(candidate.get("markdown", "")).strip()
        if not title or not markdown:
            last_error = "empty runner output"
        elif not _goal_aligned(goal, title, markdown):
            last_error = "off_goal"
            if attempt == 0:
                prompt += "\n\n????????????????????????????????????????"
        else:
            result = candidate
            break
    if not result:
        return {"status": "failed", "title": "", "markdown": "", "error": last_error}
    title = str(result.get("title", "")).strip()
    markdown = str(result.get("markdown", "")).strip()
    output.mkdir(parents=True, exist_ok=True)
    dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
    name = f"{dt.strftime('%Y-%m-%d-%H%M')}-{_safe_title(title)}.md"
    path = output / name
    header = f"# {title}\n\n> ?????{goal.get('source', 'self')} ? {goal.get('title', '')}\n> ?????{now}\n\n"
    path.write_text(header + markdown + "\n", encoding="utf-8")
    follow_up = str(result.get("follow_up", "")).strip()
    return {
        "status": "done",
        "title": title,
        "markdown": markdown,
        "error": "",
        "path": str(path),
        "follow_up": follow_up,
    }
