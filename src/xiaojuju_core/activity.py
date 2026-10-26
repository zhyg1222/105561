import json, os, re, subprocess, time
from datetime import datetime
from pathlib import Path
from .paths import Paths

PATHS = Paths.production()
NODE = Path(r"D:\Program Files\nodejs\node.exe")
DSH_BIN = Path(r"D:\yige-personal-kb\.runtime\dsh-personal\node_modules\@deepseek-ai\dsh\lib\bin.js")

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
            if result.returncode == 0:
                parsed = _parse_final(result.stdout)
                if parsed:
                    return parsed
        except Exception:
            pass
        time.sleep(1)
    return {}

def _build_prompt(goal: dict, state: dict, now: str) -> str:
    return f'''你是小居居，一个独立的 AI 互联网智能体。现在是 {now}。
当前状态：{json.dumps(state, ensure_ascii=False)}
当前目标来源：{goal.get("source", "self")}
目标标题：{goal.get("title", "自由安排")}
目标详情：{goal.get("detail", "")}

请自主完成一次安全、可验证的内部活动，例如公开网页研究、写一段观察或整理一个想法。
只允许公开网页搜索/读取和内部写作，不得发消息、发帖、登录、上传、花钱或修改账号。
如果使用了网页信息，必须保留来源 URL。没有查到就如实说明。
只输出 JSON，不要 Markdown 代码围栏：
{{"title":"成果标题","markdown":"实际成果正文，包含来源（如有）"}}
'''

def run_activity(goal: dict, state: dict, now: str, runner=None, output_dir: Path | None = None) -> dict:
    runner = runner or default_runner
    output = Path(output_dir) if output_dir else PATHS.output
    prompt = _build_prompt(goal, state, now)
    try:
        result = runner(prompt)
    except Exception as exc:
        return {"status": "failed", "title": "", "markdown": "", "error": repr(exc)}
    title = str(result.get("title", "")).strip()
    markdown = str(result.get("markdown", "")).strip()
    if not title or not markdown:
        return {"status": "failed", "title": title, "markdown": "", "error": "empty runner output"}
    output.mkdir(parents=True, exist_ok=True)
    dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
    name = f'{dt.strftime("%Y-%m-%d-%H%M")}-{_safe_title(title)}.md'
    path = output / name
    header = f'# {title}\n\n> 来源目标：{goal.get("source", "self")} · {goal.get("title", "")}\n> 执行时间：{now}\n\n'
    path.write_text(header + markdown + "\n", encoding="utf-8")
    return {"status": "done", "title": title, "markdown": markdown, "error": "", "path": str(path)}