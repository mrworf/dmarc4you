CREATE TABLE IF NOT EXISTS auth_login_throttle (
    username TEXT NOT NULL,
    source_ip TEXT NOT NULL,
    failed_count INTEGER NOT NULL,
    first_failed_at TEXT NOT NULL,
    blocked_until TEXT,
    PRIMARY KEY (username, source_ip)
);
