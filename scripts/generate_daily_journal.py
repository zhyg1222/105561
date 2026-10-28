from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from xiaojuju_agent.db import Database
from xiaojuju_agent.journal import load_json, load_jsonl, render_journal, safe_day
from xiaojuju_agent.settings import Settings
from xiaojuju_core.paths import Paths

TZ = ZoneInfo("Asia/Shanghai")


def local_time(value) -> str:
    if isinstance(value, datetime):
        return value.astimezone(TZ).strftime("%Y-%m-%d %H:%M:%S")
    return str(value or "")


async def build(day: str) -> dict:
    target = date.fromisoformat(day)
    start_local = datetime.combine(target, time.min, tzinfo=TZ)
    end_local = start_local + timedelta(days=1)
    settings = Settings.from_env()
    db = Database(settings)
    await db.open()
    try:
        async with db.transaction() as conn:
            cur = await conn.execute(
                """
                SELECT event_id, source, contact_id, payload, result, created_at
                FROM app_events
                WHERE shadow=false AND status='completed'
                  AND created_at >= %s AND created_at < %s
                ORDER BY created_at
                """,
                (start_local, end_local),
            )
            event_rows = list(await cur.fetchall())
            cur = await conn.execute(
                """
                SELECT message_id, contact_id, text, kind, status, attempts, created_at
                FROM app_outbox
                WHERE created_at >= %s AND created_at < %s
                ORDER BY created_at
                """,
                (start_local, end_local),
            )
            outbox_rows = list(await cur.fetchall())
            cur = await conn.execute(
                "SELECT status, COUNT(*) AS n FROM app_memory_candidates GROUP BY status"
            )
            memory_stats = {str(row["status"]): int(row["n"]) for row in await cur.fetchall()}
    finally:
        await db.close()

    events = [
        {
            "event_id": str(row["event_id"]),
            "source": str(row["source"] or ""),
            "contact_id": str(row["contact_id"] or "owner"),
            "user_text": str((row["payload"] or {}).get("text", "")),
            "reply": str((row["result"] or {}).get("reply", "")),
            "created_at": local_time(row["created_at"]),
        }
        for row in event_rows
    ]
    outbox = [
        {
            "message_id": str(row["message_id"]),
            "contact_id": str(row["contact_id"]),
            "text": str(row["text"]),
            "kind": str(row["kind"]),
            "status": str(row["status"]),
            "created_at": local_time(row["created_at"]),
        }
        for row in outbox_rows
    ]
    paths = Paths.production()
    activities = load_jsonl(paths.activities / f"{day}.jsonl")
    health = load_json(Path("D:/yige-personal-kb/.runtime/health/latest.json"), None)
    reflection_path = paths.reflection / f"{day}.md"
    reflection_text = reflection_path.read_text(encoding="utf-8") if reflection_path.exists() else ""
    markdown = render_journal(
        day=day,
        events=events,
        outbox=outbox,
        activities=activities,
        health=health if isinstance(health, dict) else None,
        memory_stats=memory_stats,
        reflection_text=reflection_text,
    )
    output_dir = paths.persona / "每日日录"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{day}.md"
    output_path.write_text(markdown, encoding="utf-8")
    heartbeat_dir = Path("D:/yige-personal-kb/.runtime/daily-journal")
    heartbeat_dir.mkdir(parents=True, exist_ok=True)
    (heartbeat_dir / "last_run.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now(TZ).isoformat(),
                "day": day,
                "path": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "day": day,
        "path": str(output_path),
        "events": len(events),
        "outbox": len(outbox),
        "activities": len(activities),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--day", default="")
    parser.add_argument("--previous-day", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    if args.day:
        day = safe_day(args.day)
    elif args.previous_day:
        day = (datetime.now(TZ).date() - timedelta(days=1)).isoformat()
    else:
        day = datetime.now(TZ).date().isoformat()
    print(json.dumps(asyncio.run(build(day)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()