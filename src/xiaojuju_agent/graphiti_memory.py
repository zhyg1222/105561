from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from graphiti_core import Graphiti
from graphiti_core.cross_encoder.client import CrossEncoderClient
from graphiti_core.embedder.client import EmbedderClient
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient
from graphiti_core.nodes import EpisodeType

from xiaojuju_core.contacts import contact_key

from .memory import LegacyMemoryProvider, MemoryProvider
from .settings import Settings

logger = logging.getLogger(__name__)


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


class HashEmbedder(EmbedderClient):
    """Small local n-gram embedder used until a dedicated embedding model is configured."""

    def __init__(self, dimension: int = 1024):
        self.dimension = dimension

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        value = str(text)
        for index in range(max(1, len(value) - 2)):
            gram = value[index : index + 3]
            digest = hashlib.blake2b(gram.encode("utf-8"), digest_size=8).digest()
            number = int.from_bytes(digest, "big")
            vector[number % self.dimension] += 1.0 if number & 256 else -1.0
        norm = math.sqrt(sum(item * item for item in vector)) or 1.0
        return [item / norm for item in vector]

    async def create(
        self, input_data: str | list[str] | Iterable[int] | Iterable[Iterable[int]]
    ) -> list[float]:
        if isinstance(input_data, str):
            return self._embed(input_data)
        if isinstance(input_data, (list, tuple)) and input_data:
            first = input_data[0]
            return self._embed(first if isinstance(first, str) else str(first))
        return self._embed(str(input_data))

    async def create_batch(self, input_data_list: list[str]) -> list[list[float]]:
        return [self._embed(item) for item in input_data_list]


class NoOpCrossEncoder(CrossEncoderClient):
    async def rank(self, query: str, passages: list[str]) -> list[tuple[str, float]]:
        return [(passage, 0.0) for passage in passages]


def make_graphiti(settings: Settings) -> Graphiti:
    api_key = (
        settings.deepseek_api_key.get_secret_value()
        if settings.deepseek_api_key
        else os.environ.get("DEEPSEEK_API_KEY", "")
    )
    if not api_key:
        raise RuntimeError("DeepSeek API key is required for Graphiti extraction")
    password = settings.neo4j_password
    if password is None:
        raise RuntimeError("Neo4j password is required for Graphiti")
    llm = OpenAIGenericClient(
        config=LLMConfig(
            api_key=api_key,
            model=settings.deepseek_model,
            base_url=settings.deepseek_base_url,
            temperature=0.1,
            max_tokens=4096,
        ),
        structured_output_mode="json_object",
    )
    return Graphiti(
        settings.neo4j_uri,
        settings.neo4j_user,
        password.get_secret_value(),
        llm_client=llm,
        embedder=HashEmbedder(),
        cross_encoder=NoOpCrossEncoder(),
    )


class GraphitiMemoryProvider:
    """Graphiti adapter with a fast legacy fallback.

    Graphiti extracts entities and time-valid edges asynchronously. The legacy
    provider remains the source of truth during rollout and handles outages.
    """

    def __init__(
        self,
        settings: Settings,
        legacy: MemoryProvider | None = None,
        client_factory=make_graphiti,
    ):
        self.settings = settings
        self.legacy = legacy or LegacyMemoryProvider()
        self.client_factory = client_factory
        self._client = None
        self._client_lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()

    async def _get_client(self):
        if not self.settings.graphiti_enabled:
            return None
        if self._client is not None:
            return self._client
        async with self._client_lock:
            if self._client is None:
                self._client = self.client_factory(self.settings)
        return self._client

    async def recall(self, contact: str, query: str, limit: int = 4) -> list[dict[str, Any]]:
        legacy_rows = await self.legacy.recall(contact, query, limit=limit)
        try:
            client = await self._get_client()
            if client is None:
                return legacy_rows
            group_id = "contact_" + contact_key(contact)
            edges = await asyncio.wait_for(
                client.search(query, group_ids=[group_id], num_results=limit),
                timeout=8.0,
            )
            rows = []
            for edge in edges:
                fact = str(getattr(edge, "fact", "") or "").strip()
                if fact:
                    rows.append(
                        {
                            "user": fact,
                            "assistant": "",
                            "fact": fact,
                            "valid_at": getattr(edge, "valid_at", None),
                            "invalid_at": getattr(edge, "invalid_at", None),
                            "source": "graphiti",
                        }
                    )
            combined: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in [*rows, *legacy_rows]:
                key = str(row.get("fact") or row.get("user") or "").strip()
                if not key or key in seen:
                    continue
                seen.add(key)
                combined.append(row)
            return combined[: max(limit, len(rows))]
        except Exception as exc:  # noqa: BLE001 - graph failure must fall back to legacy memory
            logger.warning("graphiti recall failed; using legacy memory: %s", exc)
            return legacy_rows

    async def remember(
        self,
        contact: str,
        user_text: str,
        assistant_text: str,
        *,
        event_id: str,
        source: str,
    ) -> dict[str, Any] | None:
        legacy_row = await self.legacy.remember(
            contact,
            user_text,
            assistant_text,
            event_id=event_id,
            source=source,
        )
        try:
            client = await self._get_client()
            if client is not None:
                task = asyncio.create_task(
                    self._background_write(
                        client,
                        contact,
                        user_text,
                        assistant_text,
                        event_id=event_id,
                        source=source,
                    )
                )
                self._background_tasks.add(task)
                task.add_done_callback(self._background_tasks.discard)
        except Exception as exc:  # noqa: BLE001 - graph failure must fall back to legacy memory
            logger.warning(
                "graphiti remember scheduled write failed; legacy memory remains: %s", exc
            )
        return legacy_row

    async def persist_candidate(self, candidate: dict[str, Any]) -> None:
        """Persist one durable queue candidate synchronously.

        This is called by the standalone ingestion worker. The legacy store is
        written first so fallback recall remains useful even if Graphiti is down.
        """

        contact = str(candidate["contact_id"])
        event_id = str(candidate["event_id"])
        await self.legacy.remember(
            contact,
            str(candidate["user_text"]),
            str(candidate["assistant_text"]),
            event_id=event_id,
            source=str(candidate["source"]),
        )
        client = await self._get_client()
        if client is None:
            raise RuntimeError("graphiti is disabled")
        await self._write_episode(
            client,
            contact,
            str(candidate["user_text"]),
            str(candidate["assistant_text"]),
            event_id=event_id,
            source=str(candidate["source"]),
            reference_time=_as_utc(candidate.get("reference_time")),
            group_id=str(candidate.get("group_id") or ("contact_" + contact_key(contact))),
        )

    async def _write_episode(
        self,
        client,
        contact: str,
        user_text: str,
        assistant_text: str,
        *,
        event_id: str,
        source: str,
        reference_time: datetime | None = None,
        group_id: str | None = None,
    ) -> None:
        target_group = group_id or ("contact_" + contact_key(contact))
        episode_name = f"conversation:{event_id}"[:80]
        if await self._episode_exists(client, episode_name, target_group):
            return
        await client.add_episode(
            name=episode_name,
            episode_body=f"\u8001\u5927\uff1a{user_text}\n\u5c0f\u5c45\u5c45\uff1a{assistant_text}",
            source=EpisodeType.message,
            source_description=source,
            reference_time=reference_time or datetime.now(UTC),
            group_id=target_group,
        )

    async def _episode_exists(self, client, name: str, group_id: str) -> bool:
        """Check the business key before retrying a partially acknowledged write."""

        driver = getattr(client, "driver", None)
        if driver is None:
            return False
        result = await driver.execute_query(
            """
            MATCH (e:Episodic {name: $name, group_id: $group_id})
            RETURN e.uuid
            LIMIT 1
            """,
            params={"name": name, "group_id": group_id},
            routing_="r",
        )
        records = getattr(result, "records", None)
        return bool(records)

    async def _background_write(
        self,
        client,
        contact: str,
        user_text: str,
        assistant_text: str,
        *,
        event_id: str,
        source: str,
    ) -> None:
        try:
            await self._write_episode(
                client,
                contact,
                user_text,
                assistant_text,
                event_id=event_id,
                source=source,
            )
        except Exception as exc:  # noqa: BLE001 - legacy memory remains available
            logger.warning("graphiti remember failed; legacy memory remains: %s", exc)

    async def drain(self) -> None:
        tasks = list(self._background_tasks)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def close(self) -> None:
        await self.drain()
        if self._client is not None:
            await self._client.close()
            self._client = None
