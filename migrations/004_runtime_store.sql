-- Runtime store for guest sessions, requirements and comparisons.
-- Applied by the ingest migration runner (same schema_migrations table).
-- Payload stays JSON text: backend models are the schema owner.

CREATE TABLE IF NOT EXISTS runtime_sessions (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_records (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    owner_session_id TEXT
);

CREATE INDEX IF NOT EXISTS runtime_records_owner_created_idx
    ON runtime_records (owner_session_id, created_at DESC, id DESC);
