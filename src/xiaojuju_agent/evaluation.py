from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Scenario:
    id: str
    category: str
    prompt: str
    max_chars: int = 160
    forbidden: tuple[str, ...] = field(default_factory=tuple)
    required_any: tuple[str, ...] = field(default_factory=tuple)


def load_scenarios(path: Path | str) -> list[Scenario]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        rows.append(
            Scenario(
                id=str(data["id"]),
                category=str(data["category"]),
                prompt=str(data["prompt"]),
                max_chars=int(data.get("max_chars", 160)),
                forbidden=tuple(data.get("forbidden", [])),
                required_any=tuple(data.get("required_any", [])),
            )
        )
    return rows


def score_reply(reply: str, scenario: Scenario) -> dict[str, Any]:
    text = re.sub(r"\s+", " ", str(reply or "")).strip()
    issues = []
    if not text:
        issues.append("empty")
    if len(text) > scenario.max_chars:
        issues.append("too_long")
    if re.search(r"(?m)^\s*(?:#{1,6}|[-*+]|\d+[.)])\s+", str(reply or "")):
        issues.append("markdown_or_list")
    for phrase in scenario.forbidden:
        if phrase and phrase in text:
            issues.append(f"forbidden:{phrase}")
    if scenario.required_any and not any(term in text for term in scenario.required_any):
        issues.append("missing_required_term")
    return {
        "id": scenario.id,
        "category": scenario.category,
        "reply": text,
        "length": len(text),
        "passed": not issues,
        "issues": issues,
    }


async def run_evaluation(
    scenarios: list[Scenario],
    call: Callable[[Scenario], Awaitable[str]],
) -> list[dict[str, Any]]:
    results = []
    for scenario in scenarios:
        try:
            reply = await call(scenario)
        except Exception as exc:  # noqa: BLE001 - evaluation records backend failures
            results.append(
                {
                    "id": scenario.id,
                    "category": scenario.category,
                    "reply": "",
                    "length": 0,
                    "passed": False,
                    "issues": ["call_failed"],
                    "error": repr(exc),
                }
            )
            continue
        results.append(score_reply(reply, scenario))
    return results


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    passed = sum(1 for result in results if result.get("passed"))
    categories: dict[str, dict[str, int]] = {}
    for result in results:
        category = str(result.get("category", "unknown"))
        bucket = categories.setdefault(category, {"passed": 0, "total": 0})
        bucket["total"] += 1
        if result.get("passed"):
            bucket["passed"] += 1
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "categories": categories,
    }
