"""CLI ingest command: content-type detection and submission."""

import base64
import gzip
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

import pytest

from cli.commands import detect_content_encoding, detect_content_type, ingest_files


class TestDetectContentType:
    """Unit tests for content type detection."""

    def test_xml_by_extension(self, tmp_path: Path) -> None:
        """File with .xml extension detected as XML."""
        f = tmp_path / "report.xml"
        f.write_bytes(b"some content")
        assert detect_content_type(f, b"some content") == "application/xml"

    def test_xml_by_prolog(self, tmp_path: Path) -> None:
        """File starting with <?xml detected as XML."""
        f = tmp_path / "report.txt"
        content = b"<?xml version='1.0'?><feedback></feedback>"
        f.write_bytes(content)
        assert detect_content_type(f, content) == "application/xml"

    def test_xml_by_feedback_tag(self, tmp_path: Path) -> None:
        """File starting with <feedback detected as XML."""
        f = tmp_path / "data"
        content = b"<feedback><report_metadata></report_metadata></feedback>"
        f.write_bytes(content)
        assert detect_content_type(f, content) == "application/xml"

    def test_xml_with_whitespace(self, tmp_path: Path) -> None:
        """XML detection handles leading whitespace."""
        f = tmp_path / "report"
        content = b"  \n  <?xml version='1.0'?><feedback/>"
        f.write_bytes(content)
        assert detect_content_type(f, content) == "application/xml"

    def test_gzip_by_extension(self, tmp_path: Path) -> None:
        """File with .gz extension detected as gzip."""
        f = tmp_path / "report.xml.gz"
        f.write_bytes(b"not really gzip")
        assert detect_content_type(f, b"not really gzip") == "application/gzip"

    def test_gzip_by_magic(self, tmp_path: Path) -> None:
        """File with gzip magic bytes detected as gzip."""
        f = tmp_path / "report"
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(b"<feedback></feedback>")
        content = buf.getvalue()
        f.write_bytes(content)
        assert detect_content_type(f, content) == "application/gzip"

    def test_zip_by_extension(self, tmp_path: Path) -> None:
        f = tmp_path / "report.zip"
        f.write_bytes(b"not really zip")
        assert detect_content_type(f, b"not really zip") == "application/zip"

    def test_zip_by_magic(self, tmp_path: Path) -> None:
        f = tmp_path / "report"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w") as archive:
            archive.writestr("report.xml", b"<feedback></feedback>")
        content = buf.getvalue()
        f.write_bytes(content)
        assert detect_content_type(f, content) == "application/zip"

    def test_detect_content_encoding_for_zip(self, tmp_path: Path) -> None:
        f = tmp_path / "report.zip"
        f.write_bytes(b"PK\x03\x04more")
        assert detect_content_encoding(f, b"PK\x03\x04more") == "zip"

    def test_mime_by_content_type_header(self, tmp_path: Path) -> None:
        """File with Content-Type header detected as MIME."""
        f = tmp_path / "email.eml"
        content = b"Content-Type: multipart/mixed;\nMIME-Version: 1.0\n\nbody"
        f.write_bytes(content)
        assert detect_content_type(f, content) == "message/rfc822"

    def test_mime_by_mime_version(self, tmp_path: Path) -> None:
        """File with MIME-Version header detected as MIME."""
        f = tmp_path / "msg"
        content = b"MIME-Version: 1.0\nFrom: sender@example.com\n\n"
        f.write_bytes(content)
        assert detect_content_type(f, content) == "message/rfc822"

    def test_unknown_fallback(self, tmp_path: Path) -> None:
        """Unknown content falls back to octet-stream."""
        f = tmp_path / "data.bin"
        content = b"\x00\x01\x02binary data"
        f.write_bytes(content)
        assert detect_content_type(f, content) == "application/octet-stream"


class TestIngestFiles:
    """Tests for ingest_files function."""

    def test_no_files_returns_false(self, capsys) -> None:
        """Empty file list returns False."""
        result = ingest_files("api_key", "http://localhost", [])
        assert result is False
        captured = capsys.readouterr()
        assert "No files specified" in captured.err

    def test_missing_file_continues(self, tmp_path: Path, capsys) -> None:
        """Missing file prints error and continues."""
        existing = tmp_path / "exists.xml"
        existing.write_bytes(b"<feedback></feedback>")
        missing = tmp_path / "missing.xml"

        with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"job_id": "job_123"}'
            mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = mock.MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = ingest_files("key", "http://localhost", [missing, existing])

        assert result is False
        captured = capsys.readouterr()
        assert "File not found: " in captured.err
        assert "exists.xml: submitted" in captured.out

    def test_successful_submission(self, tmp_path: Path, capsys) -> None:
        """Successful submission prints job_id."""
        f = tmp_path / "report.xml"
        f.write_bytes(b"<feedback></feedback>")

        with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"job_id": "job_abc123"}'
            mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = mock.MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = ingest_files("test_key", "http://example.com", [f])

        assert result is True
        captured = capsys.readouterr()
        assert "report.xml: submitted (job_id=job_abc123)" in captured.out

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("Authorization") == "Bearer test_key"
        assert req.get_header("Content-type") == "application/json"
        body = json.loads(req.data.decode("utf-8"))
        assert body["source"] == "cli"
        assert len(body["reports"]) == 1
        assert body["reports"][0]["content_type"] == "application/xml"
        assert body["reports"][0]["content_encoding"] == ""
        assert body["reports"][0]["content_transfer_encoding"] == "base64"
        decoded = base64.b64decode(body["reports"][0]["content"])
        assert decoded == b"<feedback></feedback>"

    def test_zip_submission_sets_zip_content_encoding(self, tmp_path: Path) -> None:
        f = tmp_path / "report.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, mode="w") as archive:
            archive.writestr("report.xml", b"<feedback></feedback>")
        f.write_bytes(buf.getvalue())

        with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"job_id": "job_zip123"}'
            mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = mock.MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = ingest_files("test_key", "http://example.com", [f])

        assert result is True
        req = mock_urlopen.call_args[0][0]
        body = json.loads(req.data.decode("utf-8"))
        assert body["reports"][0]["content_type"] == "application/zip"
        assert body["reports"][0]["content_encoding"] == "zip"

    def test_http_error_reports_failure(self, tmp_path: Path, capsys) -> None:
        """HTTP error prints failure message."""
        f = tmp_path / "report.xml"
        f.write_bytes(b"<feedback></feedback>")

        with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
            import urllib.error

            mock_urlopen.side_effect = urllib.error.HTTPError(
                "http://x", 403, "Forbidden", {}, io.BytesIO(b'{"detail":"Invalid API key"}')
            )

            result = ingest_files("bad_key", "http://localhost", [f])

        assert result is False
        captured = capsys.readouterr()
        assert "report.xml: failed (" in captured.err
        assert "403 Forbidden" in captured.err
        assert "Invalid API key" in captured.err

    def test_url_construction(self, tmp_path: Path) -> None:
        """URL is correctly constructed with trailing slash handling."""
        f = tmp_path / "r.xml"
        f.write_bytes(b"<feedback/>")

        with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"job_id": "j1"}'
            mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = mock.MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            ingest_files("k", "http://localhost:8000/", [f])

        req = mock_urlopen.call_args[0][0]
        assert req.full_url == "http://localhost:8000/api/v1/reports/ingest"

    def test_multiple_files_all_succeed(self, tmp_path: Path, capsys) -> None:
        """Multiple files all succeeding returns True."""
        files = []
        for i in range(3):
            f = tmp_path / f"report{i}.xml"
            f.write_bytes(f"<feedback>{i}</feedback>".encode())
            files.append(f)

        with mock.patch("cli.ingest_api.urllib.request.urlopen") as mock_urlopen:
            mock_resp = mock.MagicMock()
            mock_resp.read.return_value = b'{"job_id": "jx"}'
            mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
            mock_resp.__exit__ = mock.MagicMock(return_value=False)
            mock_urlopen.return_value = mock_resp

            result = ingest_files("k", "http://localhost", files)

        assert result is True
        assert mock_urlopen.call_count == 3
        captured = capsys.readouterr()
        assert captured.out.count("submitted") == 3


class TestMainArgParsing:
    """Tests for CLI argument parsing."""

    def test_ingest_missing_api_key_exits(self, tmp_path: Path, monkeypatch) -> None:
        """Missing API key exits with error."""
        monkeypatch.delenv("DMARC4YOU_API_KEY", raising=False)
        f = tmp_path / "r.xml"
        f.write_bytes(b"<feedback/>")

        import sys
        from cli.__main__ import main

        monkeypatch.setattr(sys, "argv", ["cli", "ingest", str(f)])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_ingest_missing_files_exits(self, monkeypatch) -> None:
        """Missing files exits with error."""
        import sys
        from cli.__main__ import main

        monkeypatch.setattr(sys, "argv", ["cli", "ingest", "--api-key", "k"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1

    def test_ingest_env_vars(self, tmp_path: Path, monkeypatch) -> None:
        """API key and URL from environment variables."""
        f = tmp_path / "r.xml"
        f.write_bytes(b"<feedback/>")

        monkeypatch.setenv("DMARC4YOU_API_KEY", "env_key")
        monkeypatch.setenv("DMARC4YOU_URL", "http://envhost:9000")

        from cli.__main__ import parse_ingest_args

        api_key, url, paths = parse_ingest_args([str(f)])
        assert api_key == "env_key"
        assert url == "http://envhost:9000"
        assert len(paths) == 1

    def test_ingest_flags_override_env(self, tmp_path: Path, monkeypatch) -> None:
        """CLI flags override environment variables."""
        f = tmp_path / "r.xml"
        f.write_bytes(b"<feedback/>")

        monkeypatch.setenv("DMARC4YOU_API_KEY", "env_key")
        monkeypatch.setenv("DMARC4YOU_URL", "http://envhost:9000")

        from cli.__main__ import parse_ingest_args

        api_key, url, paths = parse_ingest_args(
            ["--api-key", "flag_key", "--url", "http://flaghost:8080", str(f)]
        )
        assert api_key == "flag_key"
        assert url == "http://flaghost:8080"

    def test_ingest_equals_syntax(self, tmp_path: Path, monkeypatch) -> None:
        """--api-key=value and --url=value syntax works."""
        f = tmp_path / "r.xml"
        f.write_bytes(b"<feedback/>")
        monkeypatch.delenv("DMARC4YOU_API_KEY", raising=False)

        from cli.__main__ import parse_ingest_args

        api_key, url, paths = parse_ingest_args(
            ["--api-key=eq_key", "--url=http://eq:1234", str(f)]
        )
        assert api_key == "eq_key"
        assert url == "http://eq:1234"

    def test_imap_watch_env_defaults(self, monkeypatch) -> None:
        monkeypatch.setenv("DMARC_IMAP_API_KEY", "imap-key")
        monkeypatch.setenv("DMARC_IMAP_HOST", "imap.example.com")
        monkeypatch.setenv("DMARC_IMAP_USERNAME", "user@example.com")
        monkeypatch.setenv("DMARC_IMAP_PASSWORD", "secret")
        monkeypatch.setenv("DMARC_IMAP_RESTART_ON_START", "true")
        monkeypatch.setenv("DMARC_IMAP_DELETE_AFTER_DAYS", "7")

        from cli.__main__ import parse_imap_watch_args

        config = parse_imap_watch_args([])
        assert config.api_url == "http://localhost:8000"
        assert config.api_key == "imap-key"
        assert config.host == "imap.example.com"
        assert config.port == 993
        assert config.username == "user@example.com"
        assert config.password == "secret"
        assert config.restart_on_start is True
        assert config.delete_after_days == 7
        assert config.mailbox == "INBOX"

    def test_imap_watch_flags_override_env(self, monkeypatch) -> None:
        monkeypatch.setenv("DMARC_IMAP_API_KEY", "env-key")
        monkeypatch.setenv("DMARC_IMAP_HOST", "env-host")
        monkeypatch.setenv("DMARC_IMAP_USERNAME", "env-user")
        monkeypatch.setenv("DMARC_IMAP_PASSWORD", "env-pass")

        from cli.__main__ import parse_imap_watch_args

        config = parse_imap_watch_args(
            [
                "--api-url=http://api:9000",
                "--api-key=flag-key",
                "--host=imap.flag.test",
                "--port=1993",
                "--username=flag-user",
                "--password=flag-pass",
                "--mailbox=Reports",
                "--poll-seconds=30",
                "--delete-after-days=0",
                "--state-path=/tmp/imap.db",
                "--connect-timeout-seconds=12.5",
                "--job-timeout-seconds=45",
                "--restart-on-start",
            ]
        )
        assert config.api_url == "http://api:9000"
        assert config.api_key == "flag-key"
        assert config.host == "imap.flag.test"
        assert config.port == 1993
        assert config.username == "flag-user"
        assert config.password == "flag-pass"
        assert config.mailbox == "Reports"
        assert config.poll_seconds == 30
        assert config.delete_after_days == 0
        assert config.state_path == "/tmp/imap.db"
        assert config.connect_timeout_seconds == 12.5
        assert config.job_timeout_seconds == 45.0
        assert config.restart_on_start is True
