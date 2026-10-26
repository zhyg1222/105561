from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .settings import Settings


class Database:
    def __init__(self, settings: Settings):
        self.pool = AsyncConnectionPool(
            conninfo=settings.database_url,
            min_size=1,
            max_size=10,
            open=False,
            kwargs={"row_factory": dict_row},
        )

    async def open(self) -> None:
        await self.pool.open()
        await self.pool.wait()

    async def close(self) -> None:
        await self.pool.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator:
        async with self.pool.connection() as conn, conn.transaction():
            yield conn
