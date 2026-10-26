SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_events (
    event_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    kind TEXT NOT NULL,
    contact_id TEXT,
    external_id TEXT,
    payload JSONB NOT NULL,
    trace_id TEXT NOT NULL,
    traceparent TEXT NOT NULL DEFAULT '',
    timestamp TIMESTAMPTZ NOT NULL,
    shadow BOOLEAN NOT NULL DEFAULT TRUE,
    result JSONB,
    published_at TIMESTAMPTZ,
    claim_token TEXT,
    lease_expires_at TIMESTAMPTZ,
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


UPGRADE_SQL = """
ALTER TABLE app_events ADD COLUMN IF NOT EXISTS traceparent TEXT NOT NULL DEFAULT '';
ALTER TABLE app_events ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ;
ALTER TABLE app_events ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE app_events ADD COLUMN IF NOT EXISTS claim_token TEXT;
ALTER TABLE app_events ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'app_events' AND column_name = 'event_timestamp'
    ) THEN
        EXECUTE 'UPDATE app_events SET timestamp = event_timestamp WHERE timestamp IS NULL';
    END IF;
END $$;
UPDATE app_events SET timestamp = created_at WHERE timestamp IS NULL;
ALTER TABLE app_events ALTER COLUMN timestamp SET NOT NULL;
CREATE INDEX IF NOT EXISTS app_events_unpublished_idx
    ON app_events (created_at)
    WHERE published_at IS NULL AND result IS NULL AND shadow = false;
"""


async def upgrade(conn) -> None:
    await conn.execute(SCHEMA_SQL)
    await conn.execute(UPGRADE_SQL)
