import asyncio
import importlib.util
import sys
from pathlib import Path

from xiaojuju_agent.db import Database
from xiaojuju_agent.settings import Settings

if sys.platform == "win32" and hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def migrate() -> None:
    db = Database(Settings.from_env())
    await db.open()
    try:
        spec = importlib.util.spec_from_file_location(
            "platform_migration", Path("migrations/versions/0001_platform.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        async with db.transaction() as conn:
            await module.upgrade(conn)
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(migrate())
