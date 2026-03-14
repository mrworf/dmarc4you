-- API keys (DATA_MODEL): domain-bound, scope-bound; key stored as hash.
CREATE TABLE IF NOT EXISTS api_keys (
    id TEXT PRIMARY KEY,
    nickname TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    key_hash TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT,
    last_used_ip TEXT,
    last_used_user_agent TEXT,
    FOREIGN KEY (created_by_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS api_key_domains (
    api_key_id TEXT NOT NULL,
    domain_id TEXT NOT NULL,
    PRIMARY KEY (api_key_id, domain_id),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id),
    FOREIGN KEY (domain_id) REFERENCES domains(id)
);

CREATE TABLE IF NOT EXISTS api_key_scopes (
    api_key_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    PRIMARY KEY (api_key_id, scope),
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id)
);
