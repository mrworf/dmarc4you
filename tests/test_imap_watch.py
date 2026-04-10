"""Unit tests for the IMAP watcher runtime and state store."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cli.imap_watch import ImapCollector, ImapStateStore, ImapWatchConfig, _is_delete_due
from cli.ingest_api import IngestApiError


@dataclass
class FakeMessage:
    content: bytes
    internal_date: datetime
    seen: bool = False
    deleted: bool = False


class FakeMailbox:
    def __init__(self, messages: dict[str, FakeMessage], uidvalidity: str = "100") -> None:
        self.messages = messages
        self.uidvalidity = uidvalidity
        self.deleted_uids: list[str] = []

    def search_all(self) -> list[str]:
        return [uid for uid, message in sorted(self.messages.items()) if not message.deleted]

    def search_unseen(self) -> list[str]:
        return [
            uid
            for uid, message in sorted(self.messages.items())
            if not message.deleted and not message.seen
        ]

    def fetch_message(self, uid: str) -> tuple[bytes, datetime]:
        message = self.messages[uid]
        return message.content, message.internal_date

    def mark_seen(self, uid: str) -> None:
        self.messages[uid].seen = True

    def mark_unseen(self, uid: str) -> None:
        self.messages[uid].seen = False

    def hard_delete(self, uid: str) -> None:
        self.messages[uid].deleted = True
        self.deleted_uids.append(uid)


class FakeApiClient:
    def __init__(self, jobs: list[dict] | None = None, submit_error: Exception | None = None) -> None:
        self.jobs = list(jobs or [])
        self.submit_error = submit_error
        self.submissions: list[dict] = []

    def submit_report_bytes(self, **kwargs) -> str:  # type: ignore[no-untyped-def]
        self.submissions.append(kwargs)
        if self.submit_error is not None:
            raise self.submit_error
        return f"job_{len(self.submissions)}"

    def wait_for_job_terminal(self, job_id: str, **kwargs) -> dict:  # type: ignore[no-untyped-def]
        if self.jobs:
            return self.jobs.pop(0)
        return {"job_id": job_id, "state": "completed", "items": [{"status": "accepted"}]}


def build_config(tmp_path: Path, **overrides) -> ImapWatchConfig:  # type: ignore[no-untyped-def]
    base = dict(
        api_url="http://api.test",
        api_key="ingest-key",
        host="imap.example.com",
        username="user@example.com",
        password="secret",
        state_path=str(tmp_path / "imap-state.db"),
        poll_seconds=60,
    )
    base.update(overrides)
    return ImapWatchConfig(**base)


def test_state_store_tracks_uidvalidity_separately(tmp_path: Path) -> None:
    store = ImapStateStore(tmp_path / "state.db")
    internal_date = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    store.record_success("INBOX", "100", "1", internal_date, "job_a")
    store.record_success("INBOX", "200", "1", internal_date, "job_b")

    state_a = store.get_message("INBOX", "100", "1")
    state_b = store.get_message("INBOX", "200", "1")

    assert state_a is not None
    assert state_b is not None
    assert state_a.last_successful_job_id == "job_a"
    assert state_b.last_successful_job_id == "job_b"


def test_delete_due_uses_internal_date() -> None:
    now = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    internal_date = now - timedelta(days=7, minutes=1)
    assert _is_delete_due(internal_date, 7, now) is True
    assert _is_delete_due(now - timedelta(days=6, hours=23), 7, now) is False
    assert _is_delete_due(now, -1, now) is False
    assert _is_delete_due(now, 0, now) is True


def test_run_cycle_uploads_unseen_message_marks_seen_and_records_success(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    state_store = ImapStateStore(config.state_path)
    api_client = FakeApiClient()
    mailbox = FakeMailbox(
        {
            "1": FakeMessage(
                content=b"raw-email",
                internal_date=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            )
        }
    )
    collector = ImapCollector(config, state_store=state_store, api_client=api_client)

    collector.run_cycle(mailbox)

    state = state_store.get_message("INBOX", "100", "1")
    assert state is not None
    assert state.terminal_upload_outcome == "success"
    assert mailbox.messages["1"].seen is True
    assert api_client.submissions[0]["content_type"] == "message/rfc822"
    assert api_client.submissions[0]["source"] == "imap:INBOX"


def test_successful_unread_message_is_not_reuploaded(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    state_store = ImapStateStore(config.state_path)
    internal_date = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    state_store.record_success("INBOX", "100", "1", internal_date, "job_prev")
    api_client = FakeApiClient()
    mailbox = FakeMailbox({"1": FakeMessage(content=b"raw-email", internal_date=internal_date, seen=False)})
    collector = ImapCollector(config, state_store=state_store, api_client=api_client)

    collector.run_cycle(mailbox)

    assert mailbox.messages["1"].seen is True
    assert api_client.submissions == []


def test_restart_on_start_clears_state_and_marks_all_messages_unseen(tmp_path: Path) -> None:
    config = build_config(tmp_path, restart_on_start=True)
    state_store = ImapStateStore(config.state_path)
    internal_date = datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc)
    state_store.record_success("INBOX", "100", "1", internal_date, "job_prev")
    mailbox = FakeMailbox(
        {
            "1": FakeMessage(content=b"one", internal_date=internal_date, seen=True),
            "2": FakeMessage(content=b"two", internal_date=internal_date, seen=True),
        }
    )
    collector = ImapCollector(config, state_store=state_store, api_client=FakeApiClient())

    collector.run_cycle(mailbox)

    assert state_store.get_message("INBOX", "100", "1") is not None
    assert mailbox.messages["1"].seen is True
    assert mailbox.messages["2"].seen is True


def test_failed_job_leaves_message_unseen_and_not_deleted(tmp_path: Path) -> None:
    config = build_config(tmp_path, delete_after_days=0)
    state_store = ImapStateStore(config.state_path)
    api_client = FakeApiClient(
        jobs=[
            {
                "job_id": "job_1",
                "state": "completed_with_warnings",
                "items": [{"status": "rejected", "status_reason": "domain_not_configured"}],
            }
        ]
    )
    mailbox = FakeMailbox(
        {
            "1": FakeMessage(
                content=b"raw-email",
                internal_date=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            )
        }
    )
    collector = ImapCollector(config, state_store=state_store, api_client=api_client)

    collector.run_cycle(mailbox)

    state = state_store.get_message("INBOX", "100", "1")
    assert state is not None
    assert state.terminal_upload_outcome == "failed"
    assert mailbox.messages["1"].seen is False
    assert mailbox.messages["1"].deleted is False


def test_delete_after_zero_hard_deletes_after_success(tmp_path: Path) -> None:
    config = build_config(tmp_path, delete_after_days=0)
    mailbox = FakeMailbox(
        {
            "1": FakeMessage(
                content=b"raw-email",
                internal_date=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            )
        }
    )
    collector = ImapCollector(config, state_store=ImapStateStore(config.state_path), api_client=FakeApiClient())

    collector.run_cycle(mailbox)

    assert mailbox.messages["1"].deleted is True
    assert mailbox.deleted_uids == ["1"]


def test_successful_message_is_deleted_after_retention_window(tmp_path: Path) -> None:
    now = datetime(2026, 4, 10, 12, 0, tzinfo=timezone.utc)
    config = build_config(tmp_path, delete_after_days=7)
    state_store = ImapStateStore(config.state_path)
    internal_date = now - timedelta(days=8)
    state_store.record_success("INBOX", "100", "1", internal_date, "job_prev")
    mailbox = FakeMailbox({"1": FakeMessage(content=b"raw-email", internal_date=internal_date, seen=True)})
    collector = ImapCollector(
        config,
        state_store=state_store,
        api_client=FakeApiClient(),
        now_fn=lambda: now,
    )

    collector.run_cycle(mailbox)

    state = state_store.get_message("INBOX", "100", "1")
    assert state is not None
    assert state.deleted_at is not None
    assert mailbox.messages["1"].deleted is True


def test_submit_error_records_failure_and_keeps_message_unseen(tmp_path: Path) -> None:
    config = build_config(tmp_path)
    state_store = ImapStateStore(config.state_path)
    mailbox = FakeMailbox(
        {
            "1": FakeMessage(
                content=b"raw-email",
                internal_date=datetime(2026, 4, 1, 12, 0, tzinfo=timezone.utc),
            )
        }
    )
    collector = ImapCollector(
        config,
        state_store=state_store,
        api_client=FakeApiClient(submit_error=IngestApiError("boom")),
    )

    collector.run_cycle(mailbox)

    state = state_store.get_message("INBOX", "100", "1")
    assert state is not None
    assert state.terminal_upload_outcome == "failed"
    assert mailbox.messages["1"].seen is False
