SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_events (
    event_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    contact_id TEXT,
    external_id TEXT,
    payload JSONB NOT NULL,
    trace_id TEXT NOT NULL,
    shadow BOOLEAN NOT NULL DEFAULT TRUE,
    result JSONB,
    status TEXT NOT NULL DEFAULT 'received'
        CHECK (status IN ('received','queued','processing','completed','failed','denied')),
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS app_outbox (
    message_id TEXT PRIMARY KEY,
    contact_id TEXT NOT NULL,
    text TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_approvals (
    approval_id TEXT PRIMARY KEY,
    event_id TEXT REFERENCES app_events(event_id),
    tool TEXT NOT NULL,
    args JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS app_tool_runs (
    run_id TEXT PRIMARY KEY,
    event_id TEXT REFERENCES app_events(event_id),
    tool TEXT NOT NULL,
    args JSONB NOT NULL,
    result JSONB,
    status TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


async def upgrade(conn) -> None:
    await conn.execute(SCHEMA_SQL)