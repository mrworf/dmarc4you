"""Compression helpers for ingest payloads."""

from __future__ import annotations

import zipfile
from io import BytesIO

GZIP_MAGIC = b"\x1f\x8b"
ZIP_MAGIC = b"PK\x03\x04"

SUPPORTED_ZIP_EXTENSIONS = (".xml", ".gz", ".gzip", ".eml")
SUPPORTED_ZIP_CONTENT_TYPES = frozenset(
    [
        "application/xml",
        "text/xml",
        "application/gzip",
        "application/x-gzip",
        "message/rfc822",
        "application/octet-stream",
    ]
)


class ZipExtractionError(Exception):
    """Raised when a zip archive cannot be safely extracted."""


def detect_content_encoding(
    payload: bytes,
    filename: str | None = None,
    content_type: str | None = None,
) -> str | None:
    """Best-effort detection of supported compression encodings."""
    filename_lower = (filename or "").lower()
    content_type_lower = (content_type or "").lower()
    if payload[:2] == GZIP_MAGIC:
        return "gzip"
    if payload[:4] == ZIP_MAGIC:
        return "zip"
    if filename_lower.endswith(".gz") or filename_lower.endswith(".gzip"):
        return "gzip"
    if filename_lower.endswith(".zip"):
        return "zip"
    if "gzip" in content_type_lower or "x-gzip" in content_type_lower:
        return "gzip"
    if "application/zip" in content_type_lower or "x-zip-compressed" in content_type_lower:
        return "zip"
    return None


def looks_like_supported_report(payload: bytes, filename: str | None = None) -> bool:
    """Return True if a payload looks like a supported report container."""
    name = (filename or "").lower()
    if name.endswith(SUPPORTED_ZIP_EXTENSIONS):
        return True
    if detect_content_encoding(payload, filename=filename) == "gzip":
        return True
    prefix = payload[:1024].lstrip().lower()
    if prefix.startswith(b"<?xml") or prefix.startswith(b"<feedback"):
        return True
    if b"content-type:" in prefix or b"mime-version:" in prefix:
        return True
    return False


def extract_zip_members(
    data: bytes,
    *,
    max_members: int,
    max_member_bytes: int,
    max_total_bytes: int,
) -> list[dict[str, str | bytes | None]]:
    """Extract supported members from a zip archive within size limits."""
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = [info for info in archive.infolist() if not info.is_dir()]
            if len(infos) > max_members:
                raise ZipExtractionError("too_many_members")
            extracted: list[dict[str, str | bytes | None]] = []
            total_bytes = 0
            for info in infos:
                if info.flag_bits & 0x1:
                    raise ZipExtractionError("encrypted_member")
                if info.file_size > max_member_bytes:
                    raise ZipExtractionError("member_too_large")
                payload = archive.read(info)
                total_bytes += len(payload)
                if total_bytes > max_total_bytes:
                    raise ZipExtractionError("archive_too_large")
                if not looks_like_supported_report(payload, info.filename):
                    continue
                extracted.append(
                    {
                        "filename": info.filename,
                        "content": payload,
                        "content_type": _infer_member_content_type(info.filename, payload),
                        "content_encoding": detect_content_encoding(payload, filename=info.filename),
                    }
                )
            return extracted
    except zipfile.BadZipFile as exc:
        raise ZipExtractionError("bad_zip") from exc


def _infer_member_content_type(filename: str | None, payload: bytes) -> str:
    filename_lower = (filename or "").lower()
    if filename_lower.endswith(".eml"):
        return "message/rfc822"
    if filename_lower.endswith(".xml"):
        return "application/xml"
    if detect_content_encoding(payload, filename=filename) == "gzip":
        return "application/gzip"
    if detect_content_encoding(payload, filename=filename) == "zip":
        return "application/zip"
    return "application/octet-stream"
