"""Unit tests for the shared ingest API client."""

from __future__ import annotations

import io
import json
from unittest import mock

import pytest

from cli.ingest_api import (
    IngestApiClient,
    IngestApiError,
    IngestJobTimeoutError,
    is_successful_job,
)


def test_submit_report_bytes_sends_mime_payload() -> None:
    client = IngestApiClient(api_key="test-key", base_url="http://example.test")
    with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
        response = mock.MagicMock()
        response.read.return_value = b'{"job_id":"job_123"}'
        response.__enter__ = mock.MagicMock(return_value=response)
        response.__exit__ = mock.MagicMock(return_value=False)
        mock_urlopen.return_value = response

        job_id = client.submit_report_bytes(
            source="imap:INBOX",
            content=b"raw-email",
            content_type="message/rfc822",
        )

    assert job_id == "job_123"
    request = mock_urlopen.call_args[0][0]
    assert request.full_url == "http://example.test/api/v1/reports/ingest"
    body = json.loads(request.data.decode("utf-8"))
    assert body["source"] == "imap:INBOX"
    assert body["reports"][0]["content_type"] == "message/rfc822"
    assert body["reports"][0]["content_transfer_encoding"] == "base64"


def test_wait_for_job_terminal_returns_successful_job() -> None:
    client = IngestApiClient(api_key="test-key", base_url="http://example.test")
    with mock.patch.object(
        client,
        "get_job_detail",
        side_effect=[
            {"job_id": "job_123", "state": "queued"},
            {"job_id": "job_123", "state": "processing"},
            {"job_id": "job_123", "state": "completed", "items": [{"status": "accepted"}]},
        ],
    ):
        job = client.wait_for_job_terminal("job_123", timeout_seconds=30, sleep_fn=lambda _: None)

    assert job["state"] == "completed"
    assert is_successful_job(job) is True


def test_wait_for_job_terminal_timeout_raises() -> None:
    client = IngestApiClient(api_key="test-key", base_url="http://example.test")
    with mock.patch.object(client, "get_job_detail", return_value={"job_id": "job_123", "state": "queued"}):
        with pytest.raises(IngestJobTimeoutError):
            client.wait_for_job_terminal("job_123", timeout_seconds=0, sleep_fn=lambda _: None)


def test_unsuccessful_job_is_not_marked_success() -> None:
    job = {
        "job_id": "job_123",
        "state": "completed_with_warnings",
        "items": [{"status": "accepted"}, {"status": "rejected", "status_reason": "domain_not_configured"}],
    }
    assert is_successful_job(job) is False


def test_http_error_body_is_included_in_exception() -> None:
    client = IngestApiClient(api_key="test-key", base_url="http://example.test")
    with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
        import urllib.error

        mock_urlopen.side_effect = urllib.error.HTTPError(
            "http://example.test/api/v1/reports/ingest",
            403,
            "Forbidden",
            {},
            io.BytesIO(b'{"detail":"Invalid API key"}'),
        )

        with pytest.raises(IngestApiError) as exc:
            client.submit_report_bytes(source="cli", content=b"<feedback/>", content_type="application/xml")

    assert "403 Forbidden" in str(exc.value)
    assert "Invalid API key" in str(exc.value)
