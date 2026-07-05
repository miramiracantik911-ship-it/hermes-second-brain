CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    input_type TEXT NOT NULL,
    state TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'L1',
    sensitive INTEGER NOT NULL DEFAULT 0,
    instruction TEXT,
    source_url TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_events (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    from_state TEXT,
    to_state TEXT NOT NULL,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    para TEXT NOT NULL,
    code_stage TEXT NOT NULL,
    distillation_level TEXT NOT NULL,
    sensitive INTEGER NOT NULL DEFAULT 0,
    semantic_index INTEGER NOT NULL DEFAULT 1,
    current_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    note_id TEXT REFERENCES notes(id) ON DELETE SET NULL,
    url TEXT,
    source_type TEXT NOT NULL,
    accessed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT,
    extraction_status TEXT NOT NULL,
    raw_text_path TEXT
);

CREATE TABLE IF NOT EXISTS attachments (
    id TEXT PRIMARY KEY,
    note_id TEXT REFERENCES notes(id) ON DELETE SET NULL,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    path TEXT,
    temp_path TEXT,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    retention_policy TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS operations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    before_hash TEXT,
    after_hash TEXT,
    undo_payload TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_id TEXT REFERENCES jobs(id) ON DELETE CASCADE,
    operation_id TEXT REFERENCES operations(id) ON DELETE CASCADE,
    risk_level TEXT NOT NULL,
    prompt TEXT NOT NULL,
    options TEXT NOT NULL,
    decision TEXT,
    expires_at TEXT NOT NULL,
    decided_at TEXT
);

CREATE TABLE IF NOT EXISTS capabilities (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    risk_level TEXT NOT NULL,
    read_scope TEXT NOT NULL DEFAULT '[]',
    write_scope TEXT NOT NULL DEFAULT '[]',
    approval_required INTEGER NOT NULL DEFAULT 0,
    config TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sync_status (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_success_at TEXT,
    last_error TEXT,
    pending_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS search_index USING fts5(
    note_id UNINDEXED,
    title,
    body,
    tags,
    path UNINDEXED
);

