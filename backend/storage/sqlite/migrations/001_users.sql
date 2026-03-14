-- Users table for bootstrap super-admin (DATA_MODEL).
-- id: external identifier (e.g. usr_xxx); created_by_user_id NULL for bootstrap admin.

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL,
    created_at TEXT NOT NULL,
    created_by_user_id TEXT,
    last_login_at TEXT,
    disabled_at TEXT
);
