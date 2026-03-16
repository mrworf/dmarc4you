"""Unit tests for archive extraction helpers."""

import io
import zipfile

import pytest

from backend.ingest.compression import ZipExtractionError, extract_zip_members


def _build_zip(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w") as archive:
        for filename, content in entries:
            archive.writestr(filename, content)
    return buffer.getvalue()


def test_extract_zip_members_single_xml() -> None:
    payload = _build_zip([("report.xml", b"<feedback></feedback>")])
    members = extract_zip_members(payload, max_members=20, max_member_bytes=1024, max_total_bytes=2048)
    assert len(members) == 1
    assert members[0]["filename"] == "report.xml"
    assert members[0]["content_encoding"] is None


def test_extract_zip_members_multiple_and_ignore_unsupported() -> None:
    payload = _build_zip(
        [
            ("report.xml", b"<feedback></feedback>"),
            ("notes.txt", b"skip me"),
            ("message.eml", b"From: test@example.com\nMIME-Version: 1.0\n\nbody"),
        ]
    )
    members = extract_zip_members(payload, max_members=20, max_member_bytes=1024, max_total_bytes=2048)
    assert [member["filename"] for member in members] == ["report.xml", "message.eml"]


def test_extract_zip_members_rejects_oversized_member() -> None:
    payload = _build_zip([("report.xml", b"x" * 2048)])
    with pytest.raises(ZipExtractionError, match="member_too_large"):
        extract_zip_members(payload, max_members=20, max_member_bytes=1024, max_total_bytes=4096)


def test_extract_zip_members_rejects_corrupt_archive() -> None:
    with pytest.raises(ZipExtractionError, match="bad_zip"):
        extract_zip_members(b"not-a-zip", max_members=20, max_member_bytes=1024, max_total_bytes=4096)
