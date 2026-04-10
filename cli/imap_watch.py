"""IMAP inbox watcher that uploads DMARC report emails through the ingest API."""

from __future__ import annotations

import imaplib
import logging
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, Protocol

from cli.ingest_api import (
    IngestApiClient,
    IngestApiError,
    IngestJobTimeoutError,
    is_successful_job,
)

logger = logging.getLogger(__name__)

_INTERNALDATE_PATTERN = re.compile(rb'INTERNALDATE "([^"]+)"')
_UIDVALIDITY_PATTERN = re.compile(rb"\[UIDVALIDITY (\d+)\]")


@dataclass(frozen=True)
class ImapWatchConfig:
    """Configuration for the IMAP watcher runtime."""

    api_url: str
    api_key: str
    host: str
    username: str
    password: str
    port: int = 993
    mailbox: str = "INBOX"
    poll_seconds: int = 60
    restart_on_start: bool = False
    delete_after_days: int = -1
    state_path: str = "data/imap-watch-state.db"
    connect_timeout_seconds: float = 30.0
    job_timeout_seconds: float = 300.0
    job_poll_seconds: float = 2.0


@dataclass(frozen=True)
class MessageState:
    """Persisted state for one IMAP message UID."""

    mailbox: str
    uidvalidity: str
    uid: str
    internal_date: str
    last_upload_attempt_at: str | None
    last_successful_job_id: str | None
    terminal_upload_outcome: str | None
    deleted_at: str | None
    last_error: str | None


class MailboxClient(Protocol):
    """Minimal IMAP operations used by the collector."""

    uidvalidity: str

    def search_all(self) -> list[str]:
        """Return all message UIDs in the selected mailbox."""

    def search_unseen(self) -> list[str]:
        """Return unseen message UIDs in the selected mailbox."""

    def fetch_message(self, uid: str) -> tuple[bytes, datetime]:
        """Return raw RFC822 message bytes and internal date."""

    def mark_seen(self, uid: str) -> None:
        """Mark one message as seen."""

    def mark_unseen(self, uid: str) -> None:
        """Mark one message as unseen."""

    def hard_delete(self, uid: str) -> None:
        """Permanently delete one message from the selected mailbox."""


class ImapCommandError(RuntimeError):
    """Raised when an IMAP command fails or returns malformed data."""


class ImapStateStore:
    """Small SQLite store for crash-safe collector state."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS imap_message_state (
                    mailbox TEXT NOT NULL,
                    uidvalidity TEXT NOT NULL,
                    uid TEXT NOT NULL,
                    internal_date TEXT NOT NULL,
                    last_upload_attempt_at TEXT,
                    last_successful_job_id TEXT,
                    terminal_upload_outcome TEXT,
                    deleted_at TEXT,
                    last_error TEXT,
                    PRIMARY KEY (mailbox, uidvalidity, uid)
                )
                """
            )

    def clear_mailbox(self, mailbox: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM imap_message_state WHERE mailbox = ?", (mailbox,))

    def get_message(self, mailbox: str, uidvalidity: str, uid: str) -> MessageState | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT mailbox, uidvalidity, uid, internal_date, last_upload_attempt_at,
                       last_successful_job_id, terminal_upload_outcome, deleted_at, last_error
                FROM imap_message_state
                WHERE mailbox = ? AND uidvalidity = ? AND uid = ?
                """,
                (mailbox, uidvalidity, uid),
            ).fetchone()
        if row is None:
            return None
        return MessageState(**dict(row))

    def record_attempt(self, mailbox: str, uidvalidity: str, uid: str, internal_date: datetime) -> None:
        timestamp = _utc_now().isoformat()
        internal_date_iso = internal_date.astimezone(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO imap_message_state (
                    mailbox, uidvalidity, uid, internal_date, last_upload_attempt_at,
                    last_successful_job_id, terminal_upload_outcome, deleted_at, last_error
                ) VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL)
                ON CONFLICT(mailbox, uidvalidity, uid) DO UPDATE SET
                    internal_date = excluded.internal_date,
                    last_upload_attempt_at = excluded.last_upload_attempt_at,
                    terminal_upload_outcome = NULL,
                    deleted_at = NULL,
                    last_error = NULL
                """,
                (mailbox, uidvalidity, uid, internal_date_iso, timestamp),
            )

    def record_success(
        self,
        mailbox: str,
        uidvalidity: str,
        uid: str,
        internal_date: datetime,
        job_id: str,
    ) -> None:
        internal_date_iso = internal_date.astimezone(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO imap_message_state (
                    mailbox, uidvalidity, uid, internal_date, last_upload_attempt_at,
                    last_successful_job_id, terminal_upload_outcome, deleted_at, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, 'success', NULL, NULL)
                ON CONFLICT(mailbox, uidvalidity, uid) DO UPDATE SET
                    internal_date = excluded.internal_date,
                    last_upload_attempt_at = excluded.last_upload_attempt_at,
                    last_successful_job_id = excluded.last_successful_job_id,
                    terminal_upload_outcome = 'success',
                    deleted_at = NULL,
                    last_error = NULL
                """,
                (mailbox, uidvalidity, uid, internal_date_iso, _utc_now().isoformat(), job_id),
            )

    def record_failure(
        self,
        mailbox: str,
        uidvalidity: str,
        uid: str,
        internal_date: datetime,
        error: str,
    ) -> None:
        internal_date_iso = internal_date.astimezone(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO imap_message_state (
                    mailbox, uidvalidity, uid, internal_date, last_upload_attempt_at,
                    last_successful_job_id, terminal_upload_outcome, deleted_at, last_error
                ) VALUES (?, ?, ?, ?, ?, NULL, 'failed', NULL, ?)
                ON CONFLICT(mailbox, uidvalidity, uid) DO UPDATE SET
                    internal_date = excluded.internal_date,
                    last_upload_attempt_at = excluded.last_upload_attempt_at,
                    last_successful_job_id = NULL,
                    terminal_upload_outcome = 'failed',
                    deleted_at = NULL,
                    last_error = excluded.last_error
                """,
                (mailbox, uidvalidity, uid, internal_date_iso, _utc_now().isoformat(), error[:500]),
            )

    def mark_deleted(self, mailbox: str, uidvalidity: str, uid: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE imap_message_state
                SET deleted_at = ?, last_error = NULL
                WHERE mailbox = ? AND uidvalidity = ? AND uid = ?
                """,
                (_utc_now().isoformat(), mailbox, uidvalidity, uid),
            )

    def list_successful_messages(self, mailbox: str, uidvalidity: str) -> list[MessageState]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT mailbox, uidvalidity, uid, internal_date, last_upload_attempt_at,
                       last_successful_job_id, terminal_upload_outcome, deleted_at, last_error
                FROM imap_message_state
                WHERE mailbox = ? AND uidvalidity = ? AND terminal_upload_outcome = 'success' AND deleted_at IS NULL
                ORDER BY internal_date, uid
                """,
                (mailbox, uidvalidity),
            ).fetchall()
        return [MessageState(**dict(row)) for row in rows]


class ImapMailboxClient:
    """Thin `imaplib` wrapper around the selected mailbox."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        mailbox: str,
        connect_timeout_seconds: float,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._mailbox_name = mailbox
        self._connect_timeout_seconds = connect_timeout_seconds
        self._connection: imaplib.IMAP4_SSL | None = None
        self.uidvalidity = ""

    def __enter__(self) -> ImapMailboxClient:
        connection = imaplib.IMAP4_SSL(self._host, self._port, timeout=self._connect_timeout_seconds)
        self._connection = connection
        self._expect_ok(connection.login(self._username, self._password), "login")
        select_result = connection.select(self._mailbox_name, readonly=False)
        self._expect_ok(select_result, f"select {self._mailbox_name}")
        self.uidvalidity = self._resolve_uidvalidity(select_result)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._connection is None:
            return
        try:
            self._connection.close()
        except Exception:
            pass
        try:
            self._connection.logout()
        except Exception:
            pass
        self._connection = None

    def search_all(self) -> list[str]:
        return self._search("ALL")

    def search_unseen(self) -> list[str]:
        return self._search("UNSEEN")

    def fetch_message(self, uid: str) -> tuple[bytes, datetime]:
        connection = self._require_connection()
        response = connection.uid("FETCH", uid, "(BODY.PEEK[] INTERNALDATE)")
        self._expect_ok(response, f"fetch message {uid}")
        metadata = b""
        message_bytes = b""
        for item in response[1] or []:
            if isinstance(item, tuple):
                if isinstance(item[0], bytes):
                    metadata += item[0]
                if len(item) > 1 and isinstance(item[1], bytes):
                    message_bytes = item[1]
        if not message_bytes:
            raise ImapCommandError(f"FETCH for UID {uid} did not include message bytes")
        internal_date = _extract_internal_date(metadata)
        return message_bytes, internal_date

    def mark_seen(self, uid: str) -> None:
        self._store_flags(uid, "+FLAGS.SILENT", r"(\Seen)")

    def mark_unseen(self, uid: str) -> None:
        self._store_flags(uid, "-FLAGS.SILENT", r"(\Seen)")

    def hard_delete(self, uid: str) -> None:
        connection = self._require_connection()
        self._store_flags(uid, "+FLAGS.SILENT", r"(\Deleted)")
        self._expect_ok(connection.expunge(), "expunge")

    def _search(self, criteria: str) -> list[str]:
        connection = self._require_connection()
        response = connection.uid("SEARCH", None, criteria)
        self._expect_ok(response, f"search {criteria}")
        data = response[1] or []
        if not data or not data[0]:
            return []
        return [uid for uid in data[0].decode("ascii").split() if uid]

    def _store_flags(self, uid: str, mode: str, flags: str) -> None:
        connection = self._require_connection()
        self._expect_ok(connection.uid("STORE", uid, mode, flags), f"store flags {uid}")

    def _resolve_uidvalidity(self, select_result: tuple[str, list[bytes]]) -> str:
        connection = self._require_connection()
        status, data = connection.response("UIDVALIDITY")
        if status and data:
            value = data[0]
            if isinstance(value, bytes) and value:
                return value.decode("ascii", errors="replace")
        for part in select_result[1] or []:
            if isinstance(part, bytes):
                match = _UIDVALIDITY_PATTERN.search(part)
                if match:
                    return match.group(1).decode("ascii")
        raise ImapCommandError("Could not resolve UIDVALIDITY for selected mailbox")

    def _require_connection(self) -> imaplib.IMAP4_SSL:
        if self._connection is None:
            raise ImapCommandError("IMAP connection is not open")
        return self._connection

    @staticmethod
    def _expect_ok(response: tuple[str, list[bytes] | None], command: str) -> None:
        status = response[0]
        if status == "OK":
            return
        raise ImapCommandError(f"IMAP command failed for {command}: {status}")


class ImapCollector:
    """Coordinator for mailbox scanning, upload, retry, and deletion flows."""

    def __init__(
        self,
        config: ImapWatchConfig,
        *,
        state_store: ImapStateStore | None = None,
        api_client: IngestApiClient | None = None,
        mailbox_factory: Callable[[], MailboxClient] | None = None,
        now_fn: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self._config = config
        self._state_store = state_store or ImapStateStore(config.state_path)
        self._api_client = api_client or IngestApiClient(api_key=config.api_key, base_url=config.api_url)
        self._mailbox_factory = mailbox_factory or (
            lambda: ImapMailboxClient(
                config.host,
                config.port,
                config.username,
                config.password,
                config.mailbox,
                config.connect_timeout_seconds,
            )
        )
        self._now_fn = now_fn or _utc_now
        self._sleep_fn = sleep_fn or time.sleep
        self._restart_pending = config.restart_on_start

    def run_forever(self) -> None:
        """Loop forever, polling the configured mailbox on the requested cadence."""
        while True:
            try:
                with self._mailbox_factory() as mailbox:
                    self.run_cycle(mailbox)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logger.exception("IMAP collector cycle failed: %s", exc)
            self._sleep_fn(self._config.poll_seconds)

    def run_cycle(self, mailbox: MailboxClient) -> None:
        """Run one poll cycle against an already opened mailbox."""
        uidvalidity = mailbox.uidvalidity
        if self._restart_pending:
            self._handle_restart(mailbox)
            self._restart_pending = False
        all_uids = set(mailbox.search_all())
        unseen_uids = mailbox.search_unseen()
        for uid in unseen_uids:
            self._process_unseen_message(mailbox, uidvalidity, uid)
        self._delete_due_messages(mailbox, uidvalidity, all_uids)

    def _handle_restart(self, mailbox: MailboxClient) -> None:
        logger.info("Restart-on-start enabled; clearing state and marking mailbox unread")
        self._state_store.clear_mailbox(self._config.mailbox)
        for uid in mailbox.search_all():
            mailbox.mark_unseen(uid)

    def _process_unseen_message(self, mailbox: MailboxClient, uidvalidity: str, uid: str) -> None:
        state = self._state_store.get_message(self._config.mailbox, uidvalidity, uid)
        if state and state.terminal_upload_outcome == "success" and not state.deleted_at:
            mailbox.mark_seen(uid)
            logger.info("Message UID %s already uploaded successfully; marking seen", uid)
            return

        try:
            raw_message, internal_date = mailbox.fetch_message(uid)
            self._state_store.record_attempt(self._config.mailbox, uidvalidity, uid, internal_date)
            job_id = self._api_client.submit_report_bytes(
                source=f"imap:{self._config.mailbox}",
                content=raw_message,
                content_type="message/rfc822",
            )
            logger.info("Uploaded UID %s as job %s", uid, job_id)
            job = self._api_client.wait_for_job_terminal(
                job_id,
                timeout_seconds=self._config.job_timeout_seconds,
                poll_interval_seconds=self._config.job_poll_seconds,
                sleep_fn=self._sleep_fn,
            )
            if not is_successful_job(job):
                error = _job_failure_message(job)
                self._state_store.record_failure(self._config.mailbox, uidvalidity, uid, internal_date, error)
                logger.warning("Job %s for UID %s completed with retryable failure: %s", job_id, uid, error)
                return

            self._state_store.record_success(self._config.mailbox, uidvalidity, uid, internal_date, job_id)
            mailbox.mark_seen(uid)
            logger.info("UID %s processed successfully", uid)
            if _is_delete_due(internal_date, self._config.delete_after_days, self._now_fn()):
                mailbox.hard_delete(uid)
                self._state_store.mark_deleted(self._config.mailbox, uidvalidity, uid)
                logger.info("UID %s deleted from mailbox after successful upload", uid)
        except (IngestApiError, IngestJobTimeoutError, ImapCommandError) as exc:
            logger.warning("UID %s will be retried later: %s", uid, exc)
            if "internal_date" in locals():
                self._state_store.record_failure(
                    self._config.mailbox,
                    uidvalidity,
                    uid,
                    internal_date,
                    str(exc),
                )

    def _delete_due_messages(self, mailbox: MailboxClient, uidvalidity: str, all_uids: set[str]) -> None:
        if self._config.delete_after_days < 0:
            return
        now = self._now_fn()
        for state in self._state_store.list_successful_messages(self._config.mailbox, uidvalidity):
            if not _is_delete_due(datetime.fromisoformat(state.internal_date), self._config.delete_after_days, now):
                continue
            if state.uid not in all_uids:
                self._state_store.mark_deleted(self._config.mailbox, uidvalidity, state.uid)
                continue
            mailbox.hard_delete(state.uid)
            self._state_store.mark_deleted(self._config.mailbox, uidvalidity, state.uid)
            logger.info("Deleted previously uploaded UID %s after retention delay", state.uid)


def run_imap_watch(config: ImapWatchConfig) -> None:
    """Entry point for the standalone IMAP collector runtime."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    collector = ImapCollector(config)
    collector.run_forever()


def _extract_internal_date(metadata: bytes) -> datetime:
    match = _INTERNALDATE_PATTERN.search(metadata)
    if not match:
        raise ImapCommandError("FETCH response did not include INTERNALDATE")
    internal_date = parsedate_to_datetime(match.group(1).decode("ascii", errors="replace"))
    if internal_date.tzinfo is None:
        return internal_date.replace(tzinfo=timezone.utc)
    return internal_date


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_delete_due(internal_date: datetime, delete_after_days: int, now: datetime) -> bool:
    if delete_after_days < 0:
        return False
    if delete_after_days == 0:
        return True
    return now >= internal_date.astimezone(timezone.utc) + timedelta(days=delete_after_days)


def _job_failure_message(job: dict) -> str:
    items = job.get("items")
    if not isinstance(items, list) or not items:
        return f"Job {job.get('job_id', 'unknown')} completed without items"
    statuses = []
    for item in items:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "unknown")
        reason = str(item.get("status_reason") or "").strip()
        statuses.append(f"{status}:{reason}" if reason else status)
    return ", ".join(statuses) if statuses else "Job completed without successful items"
