from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "apps" / "phone_agent"))

import phone_agent as phone

from xiaojuju_agent.db import Database
from xiaojuju_agent.outbox import OutboxStore
from xiaojuju_agent.settings import Settings

OWNER_ALIASES = {"owner", "boss", "老大"}


def chat_contact(contact_id: str) -> str:
    return phone.PERSONA_CHAT_TITLE if contact_id in OWNER_ALIASES else contact_id


async def run_once(outbox: OutboxStore) -> bool:
    row = await outbox.claim_next()
    if row is None:
        return False
    contact_id = str(row["contact_id"])
    contact = chat_contact(contact_id)
    text = str(row["text"])
    try:
        ok = await asyncio.to_thread(phone.send_text, text, None, contact)
    except Exception as exc:  # noqa: BLE001 - phone failures must become retryable receipts
        ok = False
        error = repr(exc)
    else:
        error = "send failed" if not ok else ""
    if ok:
        await outbox.mark_sent(row["message_id"])
        state = phone.load_state(contact)
        phone.append_history_message(
            state.setdefault("history", []),
            "assistant",
            text,
        )
        phone.save_state(state, contact)
        phone.log(f"[{contact}] agent outbox sent: {row['message_id']}")
        return True
    if int(row.get("attempts", 0)) >= 3:
        await outbox.mark_failed(row["message_id"], error)
        phone.log(f"[{contact}] agent outbox failed permanently: {row['message_id']} {error}")
    else:
        await outbox.mark_retry(row["message_id"], error)
        phone.log(f"[{contact}] agent outbox retry queued: {row['message_id']} {error}")
    return False


async def run_loop(outbox: OutboxStore, interval: float) -> None:
    while True:
        await outbox.recover_stale()
        await run_once(outbox)
        await asyncio.sleep(max(1.0, interval))


async def main_async(args) -> int:
    settings = Settings.from_env()
    db = Database(settings)
    await db.open()
    outbox = OutboxStore(db)
    lock = phone.acquire_instance_lock()
    if not lock:
        print("phone worker already owns the phone", flush=True)
        await db.close()
        return 2
    try:
        await outbox.recover_stale()
        if args.loop:
            await run_loop(outbox, args.interval)
            return 0
        changed = await run_once(outbox)
        return 0 if changed else 1
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=float, default=5.0)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
