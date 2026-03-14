-- Sessions: server-side session store (id = session token in cookie).
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Audit log: minimal fields for login events (DATA_MODEL).
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_user_id TEXT,
    actor_api_key_id TEXT,
    action_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    source_ip TEXT,
    user_agent TEXT,
    summary TEXT,
    metadata_json TEXT
);
