from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from xiaojuju_agent.db import Database
from xiaojuju_agent.graphiti_memory import GraphitiMemoryProvider
from xiaojuju_agent.memory import LegacyMemoryProvider
from xiaojuju_agent.memory_queue import MemoryIngestionWorker, MemoryQueueStore
from xiaojuju_agent.settings import Settings

logger = logging.getLogger(__name__)
def _acquire_lock():
    if sys.platform != "win32":
        return object()
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, r"Local\XiaoJuJuMemoryWorker")
    if not handle:
        return None
    if kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        kernel32.CloseHandle(handle)
        return None
    return handle


def _release_lock(handle) -> None:
    if sys.platform == "win32" and handle is not None:
        import ctypes

        ctypes.windll.kernel32.CloseHandle(handle)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drain durable memory candidates into Graphiti")
    parser.add_argument("--once", action="store_true", help="process at most one candidate and exit")
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--lease-seconds", type=int, default=300)
    parser.add_argument("--max-attempts", type=int, default=5)
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    settings = Settings.from_env()
    db = Database(settings)
    await db.open()
    provider = GraphitiMemoryProvider(settings) if settings.graphiti_enabled else LegacyMemoryProvider()
    queue = MemoryQueueStore(db)
    worker = MemoryIngestionWorker(
        queue,
        provider,
        poll_interval_seconds=args.poll_seconds,
        lease_seconds=args.lease_seconds,
        max_attempts=args.max_attempts,
    )
    try:
        if args.once:
            worked = await worker.run_once()
            print("processed" if worked else "empty")
            return 0 if worked else 1
        logger.info("memory ingestion worker started")
        await worker.run_forever()
        return 0
    finally:
        close = getattr(provider, "close", None)
        if close is not None:
            await close()
        await db.close()


def main() -> None:
    if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    lock = _acquire_lock()
    if lock is None:
        print("memory worker already running")
        return
    try:
        raise SystemExit(asyncio.run(_run(args)))
    finally:
        _release_lock(lock)


if __name__ == "__main__":
    main()
