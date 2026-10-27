from __future__ import annotations

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

BROWSER_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "browser_read.js"
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
    if not BROWSER_SCRIPT.is_file():
        raise RuntimeError("browser_read.js is missing")
    if not CHROME.is_file():
        raise RuntimeError("Chrome is missing")
    env = os.environ.copy()
    env["XJJ_PUPPETEER_PATH"] = str(PUPPETEER)
    env["XJJ_CHROME_PATH"] = str(CHROME)
    env["XJJ_BROWSER_PROFILE"] = str(PROFILE)
    result = subprocess.run(
        [node, str(BROWSER_SCRIPT), url],
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
