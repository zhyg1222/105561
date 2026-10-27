from __future__ import annotations

import argparse
import asyncio
import json
import sys

from xiaojuju_agent.db import Database
from xiaojuju_agent.memory_queue import MemoryQueueStore, build_memory_candidate
from xiaojuju_agent.settings import Settings

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
)


def should_reconcile(event_id: str) -> bool:
    value = str(event_id)
    return not any(value.startswith(prefix) for prefix in EXCLUDED_PREFIXES)


async def run(args) -> dict:
    settings = Settings.from_env()
    db = Database(settings)
    await db.open()
    try:
        sources = [item.strip() for item in args.sources.split(",") if item.strip()]
        async with db.transaction() as conn:
            cur = await conn.execute(
                """
                SELECT event_id, timestamp, source, contact_id, payload, result
                FROM app_events e
                WHERE status='completed' AND shadow=false
                  AND source = ANY(%s)
                  AND result IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM app_memory_candidates c WHERE c.event_id=e.event_id
                  )
                ORDER BY created_at
                LIMIT %s
                """,
                (sources, int(args.limit)),
            )
            rows = list(await cur.fetchall())
        candidates = [
            row
            for row in rows
            if should_reconcile(row["event_id"])
            and (row["payload"].get("text") or "")
            and (row["result"].get("reply") or "")
        ]
        if args.apply:
            queue = MemoryQueueStore(db)
            for row in candidates:
                contact = str(row["contact_id"] or "owner")
                await queue.enqueue(
                    build_memory_candidate(
                        event_id=str(row["event_id"]),
                        contact=contact,
                        user_text=str(row["payload"].get("text", "")),
                        assistant_text=str(row["result"].get("reply", "")),
                        source=str(row["source"]),
                        reference_time=row["timestamp"],
                    )
                )
        return {
            "dry_run": not args.apply,
            "found": len(rows),
            "eligible": len(candidates),
            "event_ids": [str(row["event_id"]) for row in candidates],
        }
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="wechat,live,browser")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()