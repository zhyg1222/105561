from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from langchain_core.tools import StructuredTool

from .contracts import PolicyInput
from .tools import ToolExecution, ToolExecutor
from .web import is_public_url

BROWSER_READ_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "browser_read.js"
BROWSER_ACTION_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "browser_act.js"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PUPPETEER = Path(
    r"D:\yige-personal-kb\.runtime\dsh-personal\home\profiles\personal\node_modules\puppeteer-core"
)
PROFILE = Path(r"D:\yige-personal-kb\.runtime\browser-worker-profile")


def default_browser_read(url: str) -> dict:
    if not is_public_url(url):
        raise ValueError("only public http(s) URLs are allowed")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for browser read")
    if not BROWSER_READ_SCRIPT.is_file():
        raise RuntimeError("browser_read.js is missing")
    if not CHROME.is_file():
        raise RuntimeError("Chrome is missing")
    env = os.environ.copy()
    env["XJJ_PUPPETEER_PATH"] = str(PUPPETEER)
    env["XJJ_CHROME_PATH"] = str(CHROME)
    env["XJJ_BROWSER_PROFILE"] = str(PROFILE)
    result = subprocess.run(
        [node, str(BROWSER_READ_SCRIPT), url],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=45,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:] or "browser read failed")
    return json.loads(result.stdout)


class BrowserReadTool:
    """Read a rendered public page with a headless Chrome profile."""

    def __init__(
        self,
        executor: ToolExecutor,
        read_fn: Callable[[str], dict] = default_browser_read,
    ):
        self.executor = executor
        self.read_fn = read_fn

    async def read(
        self,
        url: str,
        *,
        source: str = "browser",
        shadow: bool = False,
    ) -> ToolExecution:
        if not is_public_url(url):
            raise ValueError("only public http(s) URLs are allowed")
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="browser.read",
            args={"url": url},
            risk="read_only",
            shadow=shadow,
            side_effect=False,
        )
        return await self.executor.execute(call, lambda: self.read_fn(url))


def as_langchain_browser_tool(tool: BrowserReadTool) -> StructuredTool:
    async def _read(url: str) -> str:
        execution = await tool.read(url)
        if not execution.executed:
            return f"browser read denied: {execution.decision.reason}"
        return json.dumps(execution.result, ensure_ascii=False)

    return StructuredTool.from_function(
        name="browser_read",
        description="Read a rendered public web page. Read-only; private URLs are rejected.",
        coroutine=_read,
    )


def validate_actions(actions: list[dict]) -> list[dict]:
    if not isinstance(actions, list) or not actions or len(actions) > 20:
        raise ValueError("actions must be a non-empty list of at most 20 items")
    allowed = {"navigate", "click", "type", "press", "wait"}
    for action in actions:
        if not isinstance(action, dict) or action.get("action") not in allowed:
            raise ValueError("unsupported browser action")
        if action["action"] == "navigate" and not is_public_url(str(action.get("url", ""))):
            raise ValueError("navigate requires a public http(s) URL")
        if action["action"] == "click" and not str(action.get("selector", "")).strip():
            raise ValueError("click requires selector")
        if action["action"] == "type" and (
            not str(action.get("selector", "")).strip() or not isinstance(action.get("text"), str)
        ):
            raise ValueError("type requires selector and text")
        if action["action"] == "press" and not str(action.get("key", "")).strip():
            raise ValueError("press requires key")
    return actions


def default_browser_action(actions: list[dict]) -> dict:
    actions = validate_actions(actions)
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for browser action")
    if not BROWSER_ACTION_SCRIPT.is_file():
        raise RuntimeError("browser_act.js is missing")
    if not CHROME.is_file():
        raise RuntimeError("Chrome is missing")
    env = os.environ.copy()
    env["XJJ_PUPPETEER_PATH"] = str(PUPPETEER)
    env["XJJ_CHROME_PATH"] = str(CHROME)
    env["XJJ_BROWSER_PROFILE"] = str(PROFILE)
    encoded = base64.b64encode(json.dumps(actions, ensure_ascii=False).encode("utf-8")).decode(
        "ascii"
    )
    result = subprocess.run(
        [node, str(BROWSER_ACTION_SCRIPT), encoded],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:] or "browser action failed")
    return json.loads(result.stdout)


class BrowserActionTool:
    """Approval-gated browser actions; it never executes in shadow mode."""

    def __init__(
        self,
        executor: ToolExecutor,
        action_fn: Callable[[list[dict]], dict] = default_browser_action,
    ):
        self.executor = executor
        self.action_fn = action_fn

    async def act(
        self,
        actions: list[dict],
        *,
        source: str = "browser",
        event_id: str | None = None,
        shadow: bool = False,
        approval: str | None = None,
    ) -> ToolExecution:
        actions = validate_actions(actions)
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="browser.action",
            args={"actions": actions},
            event_id=event_id,
            risk="external",
            shadow=shadow,
            side_effect=True,
        )
        return await self.executor.execute(
            call,
            lambda: self.action_fn(actions),
            approval=approval,
        )


def as_langchain_action_tool(tool: BrowserActionTool) -> StructuredTool:
    async def _act(actions: list[dict]) -> str:
        execution = await tool.act(actions)
        if not execution.executed:
            return json.dumps(
                {
                    "executed": False,
                    "reason": execution.decision.reason,
                    "approval": execution.result,
                },
                ensure_ascii=False,
            )
        return json.dumps({"executed": True, "result": execution.result}, ensure_ascii=False)

    return StructuredTool.from_function(
        name="browser_action",
        description="Propose a browser action plan. Side effects require explicit one-time approval.",
        coroutine=_act,
    )
