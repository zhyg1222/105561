# Memory Ingestion Research and Decision

> Date: 2026-10-27  
> Goal: close the crash window between an Agent event completing and its Graphiti episode being written, without adding an unnecessary distributed system.

## Findings

- Graphiti `add_episode` performs entity extraction, relation extraction, deduplication, embedding and graph writes. Its own documentation recommends running it in the background, sequentially, and using a task queue such as Celery for web applications.
- Graphiti does not include a durable ingestion queue in the installed `0.31.2` package. The API expects the caller to provide retry and ordering semantics.
- A transactional outbox is the appropriate fit when the source event lives in PostgreSQL: write the event result and a queue row in one transaction, then let a separate worker claim and process the row.
- PostgreSQL `FOR UPDATE SKIP LOCKED` gives safe multi-worker claiming without turning Redis into a second source of truth.
- The project already has PostgreSQL, Celery and Valkey. Adding Kafka, Temporal or a second memory service would increase operational risk without improving this single-node workload.

## Decision

Reuse the existing stack:

1. `app_events` and `app_memory_candidates` commit atomically.
2. A standalone worker polls the queue and calls Graphiti sequentially.
3. A business key (`conversation:<event_id>` plus `group_id`) makes retries idempotent after a partial Graphiti write.
4. Failures use bounded retry with exponential backoff and end in a visible `failed` state.
5. The legacy SQLite/JSONL memory remains the fast fallback and is written by the same worker.

This is a small transactional-outbox adapter around Graphiti, not a second memory engine.

## Evidence

- Unit and integration tests: 148 passed.
- Real queue candidate: `queue-smoke-20261027-1`.
- The candidate was marked `done` only after the real Neo4j episode existed.
- A deliberate replay found the existing episode and did not create a duplicate.
- Neo4j business key: `conversation:queue-smoke-20261027-1`.

## Sources

- Graphiti repository: https://github.com/getzep/graphiti
- Graphiti adding episodes: https://help.getzep.com/graphiti/core-concepts/adding-episodes
- Graphiti slow-ingestion discussion: https://github.com/getzep/graphiti/issues/186
- Transactional outbox pattern: https://microservices.io/patterns/data/transactional-outbox.html