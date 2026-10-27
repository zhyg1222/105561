from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from langchain_core.tools import StructuredTool

from .contracts import PolicyInput
from .tools import ToolExecution, ToolExecutor

ANYSEARCH = Path(r"C:\Users\Administrator\.codex\skills\anysearch\scripts\anysearch_cli.js")


def default_public_search(query: str, max_results: int = 5) -> str:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for public web search")
    result = subprocess.run(
        [
            node,
            str(ANYSEARCH),
            "search",
            str(query),
            "--max_results",
            str(max(1, min(int(max_results), 10))),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:] or "public search failed")
    return result.stdout.strip()


class WebSearchTool:
    """Read-only public research tool. It never logs in or publishes."""

    def __init__(
        self,
        executor: ToolExecutor,
        search_fn: Callable[[str, int], str] = default_public_search,
    ):
        self.executor = executor
        self.search_fn = search_fn

    async def search(
        self,
        query: str,
        *,
        source: str = "browser",
        shadow: bool = False,
        max_results: int = 5,
    ) -> ToolExecution:
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="web.search",
            args={"query": query, "max_results": max_results},
            risk="read_only",
            shadow=shadow,
            side_effect=False,
        )
        return await self.executor.execute(
            call,
            lambda: self.search_fn(query, max_results),
        )


def as_langchain_tool(tool: WebSearchTool) -> StructuredTool:
    async def _run(query: str, max_results: int = 5) -> str:
        execution = await tool.search(query, max_results=max_results)
        if not execution.executed:
            return f"search denied: {execution.decision.reason}"
        return str(execution.result)

    return StructuredTool.from_function(
        name="web_search",
        description="Search the public web for current public facts. Read-only, never logs in or publishes.",
        coroutine=_run,
    )
