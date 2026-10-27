from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

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


def is_public_url(url: str) -> bool:
    parsed = urlparse(str(url))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    host = parsed.hostname.lower().strip(".")
    if host == "localhost" or host.endswith((".local", ".internal")):
        return False
    if host in {"127.0.0.1", "::1", "0.0.0.0"}:
        return False
    parts = host.split(".")
    if len(parts) == 4 and all(part.isdigit() for part in parts):
        octets = [int(part) for part in parts]
        if octets[0] == 10 or octets[0] == 127:
            return False
        if octets[0] == 192 and octets[1] == 168:
            return False
        if octets[0] == 172 and 16 <= octets[1] <= 31:
            return False
        if octets[0] == 169 and octets[1] == 254:
            return False
    return True


def default_public_fetch(url: str) -> str:
    if not is_public_url(url):
        raise ValueError("only public http(s) URLs are allowed")
    node = shutil.which("node")
    if not node:
        raise RuntimeError("node is required for public web fetch")
    result = subprocess.run(
        [node, str(ANYSEARCH), "extract", str(url)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-1000:] or "public fetch failed")
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


class WebFetchTool:
    """Policy-gated public URL reader with local-network SSRF protection."""

    def __init__(
        self, executor: ToolExecutor, fetch_fn: Callable[[str], str] = default_public_fetch
    ):
        self.executor = executor
        self.fetch_fn = fetch_fn

    async def fetch(
        self, url: str, *, source: str = "browser", shadow: bool = False
    ) -> ToolExecution:
        if not is_public_url(url):
            raise ValueError("only public http(s) URLs are allowed")
        call = PolicyInput(
            actor="xiaojuju",
            source=source,
            tool="web.fetch",
            args={"url": url},
            risk="read_only",
            shadow=shadow,
            side_effect=False,
        )
        return await self.executor.execute(call, lambda: self.fetch_fn(url))


def as_langchain_tools(
    search_tool: WebSearchTool, fetch_tool: WebFetchTool
) -> list[StructuredTool]:
    async def _search(query: str, max_results: int = 5) -> str:
        execution = await search_tool.search(query, max_results=max_results)
        if not execution.executed:
            return f"search denied: {execution.decision.reason}"
        return str(execution.result)

    async def _fetch(url: str) -> str:
        execution = await fetch_tool.fetch(url)
        if not execution.executed:
            return f"fetch denied: {execution.decision.reason}"
        return str(execution.result)

    return [
        StructuredTool.from_function(
            name="web_search",
            description="Search the public web for current public facts. Read-only.",
            coroutine=_search,
        ),
        StructuredTool.from_function(
            name="web_fetch",
            description="Read a public http(s) page. Private and local URLs are rejected.",
            coroutine=_fetch,
        ),
    ]
