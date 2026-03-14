"""Parse MIME email messages and extract DMARC report attachments."""

import email
import email.policy
from email.message import EmailMessage

MAX_ATTACHMENTS = 20
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB per attachment

REPORT_CONTENT_TYPES = frozenset([
    "application/xml",
    "text/xml",
    "application/gzip",
    "application/x-gzip",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",
])


def is_mime_message(data: bytes) -> bool:
    """Detect if data looks like a MIME email message (not raw XML)."""
    if not data:
        return False
    prefix = data[:1024]
    try:
        text = prefix.decode("utf-8", errors="ignore")
    except Exception:
        return False
    lower = text.lower()
    if lower.lstrip().startswith("<?xml") or lower.lstrip().startswith("<feedback"):
        return False
    lines = text.split("\n")
    header_count = 0
    for line in lines[:30]:
        line_lower = line.lower()
        if line_lower.startswith("from:"):
            header_count += 1
        elif line_lower.startswith("to:"):
            header_count += 1
        elif line_lower.startswith("subject:"):
            header_count += 1
        elif line_lower.startswith("mime-version:"):
            header_count += 1
        elif line_lower.startswith("content-type:"):
            header_count += 1
        elif line_lower.startswith("date:"):
            header_count += 1
    return header_count >= 2


def extract_attachments(data: bytes) -> list[dict]:
    """Parse MIME message and extract report attachments.

    Returns list of dicts with:
      - content: bytes (raw attachment content, possibly still compressed)
      - content_type: str
      - filename: str | None
      - content_encoding: str | None ('gzip' if appears compressed)
    """
    if len(data) > 50 * 1024 * 1024:
        return []
    try:
        msg = email.message_from_bytes(data, policy=email.policy.default)
    except Exception:
        return []

    attachments: list[dict] = []
    _extract_from_part(msg, attachments)
    return attachments[:MAX_ATTACHMENTS]


def _extract_from_part(part: EmailMessage, attachments: list[dict]) -> None:
    """Recursively extract attachments from a MIME part."""
    if len(attachments) >= MAX_ATTACHMENTS:
        return

    content_type = part.get_content_type() or ""
    content_type_lower = content_type.lower()

    if part.is_multipart():
        for subpart in part.iter_parts():
            _extract_from_part(subpart, attachments)
        return

    if content_type_lower not in REPORT_CONTENT_TYPES:
        return

    try:
        payload = part.get_payload(decode=True)
    except Exception:
        return

    if payload is None:
        return
    if not isinstance(payload, bytes):
        return
    if len(payload) > MAX_ATTACHMENT_BYTES:
        return

    filename = part.get_filename() or ""
    content_encoding = _detect_encoding(payload, filename, content_type_lower)

    attachments.append({
        "content": payload,
        "content_type": content_type,
        "filename": filename or None,
        "content_encoding": content_encoding,
    })


def _detect_encoding(payload: bytes, filename: str, content_type: str) -> str | None:
    """Detect if payload is gzip/zip compressed."""
    if payload[:2] == b"\x1f\x8b":
        return "gzip"
    filename_lower = filename.lower()
    if filename_lower.endswith(".gz") or filename_lower.endswith(".gzip"):
        return "gzip"
    if "gzip" in content_type or "x-gzip" in content_type:
        return "gzip"
    return None
