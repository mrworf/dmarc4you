ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN password_changed_at TEXT;

UPDATE users
SET must_change_password = 0
WHERE must_change_password IS NULL;
