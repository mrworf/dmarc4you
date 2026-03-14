-- Allow actor_user_id NULL for API-key jobs (ingest_jobs.actor_user_id was NOT NULL).
-- SQLite does not support ALTER COLUMN; recreate table.

CREATE TABLE IF NOT EXISTS _ingest_jobs_new (
    id TEXT PRIMARY KEY,
    actor_type TEXT NOT NULL DEFAULT 'user',
    actor_user_id TEXT,
    actor_api_key_id TEXT,
    submitted_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    state TEXT NOT NULL DEFAULT 'queued',
    last_error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);

INSERT INTO _ingest_jobs_new (id, actor_type, actor_user_id, actor_api_key_id, submitted_at, started_at, completed_at, state, last_error, retry_count)
SELECT id, actor_type, actor_user_id, actor_api_key_id, submitted_at, started_at, completed_at, state, last_error, retry_count FROM ingest_jobs;

DROP TABLE ingest_jobs;

ALTER TABLE _ingest_jobs_new RENAME TO ingest_jobs;
