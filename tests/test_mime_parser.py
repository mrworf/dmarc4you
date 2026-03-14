"""Unit tests for MIME email parsing."""

import gzip

from backend.ingest.mime_parser import is_mime_message, extract_attachments


SAMPLE_AGGREGATE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>example.org</org_name>
    <report_id>test123</report_id>
    <date_range><begin>1704067200</begin><end>1704153600</end></date_range>
  </report_metadata>
  <policy_published><domain>example.com</domain></policy_published>
  <record>
    <row><source_ip>192.0.2.1</source_ip><count>5</count>
      <policy_evaluated><disposition>none</disposition><dkim>pass</dkim><spf>pass</spf></policy_evaluated>
    </row>
    <identifiers><header_from>example.com</header_from></identifiers>
  </record>
</feedback>"""


def _make_mime_email(attachments: list[tuple[str, str, bytes]]) -> bytes:
    """Build a simple multipart/mixed MIME message with given attachments.
    
    attachments: list of (filename, content_type, content_bytes)
    """
    boundary = "----=_Part_12345"
    parts = []
    for filename, content_type, content in attachments:
        import base64
        encoded = base64.b64encode(content).decode("ascii")
        part = (
            f'--{boundary}\r\n'
            f'Content-Type: {content_type}; name="{filename}"\r\n'
            f'Content-Disposition: attachment; filename="{filename}"\r\n'
            f'Content-Transfer-Encoding: base64\r\n'
            f'\r\n'
            f'{encoded}\r\n'
        )
        parts.append(part)
    body = "".join(parts) + f'--{boundary}--\r\n'
    headers = (
        f'From: reporter@example.org\r\n'
        f'To: dmarc@example.com\r\n'
        f'Subject: DMARC Report\r\n'
        f'MIME-Version: 1.0\r\n'
        f'Content-Type: multipart/mixed; boundary="{boundary}"\r\n'
        f'\r\n'
    )
    return (headers + body).encode("utf-8")


class TestIsMimeMessage:
    def test_detects_multipart_email(self):
        email = _make_mime_email([("report.xml", "application/xml", SAMPLE_AGGREGATE_XML)])
        assert is_mime_message(email) is True

    def test_rejects_plain_xml(self):
        assert is_mime_message(SAMPLE_AGGREGATE_XML) is False

    def test_rejects_xml_with_leading_whitespace(self):
        data = b"  \n  <?xml version='1.0'?><feedback></feedback>"
        assert is_mime_message(data) is False

    def test_rejects_feedback_root(self):
        data = b"<feedback><report_metadata></report_metadata></feedback>"
        assert is_mime_message(data) is False

    def test_rejects_empty(self):
        assert is_mime_message(b"") is False

    def test_detects_minimal_headers(self):
        data = b"From: a@b.com\r\nTo: c@d.com\r\nSubject: Test\r\n\r\nBody"
        assert is_mime_message(data) is True


class TestExtractAttachments:
    def test_single_xml_attachment(self):
        email = _make_mime_email([("report.xml", "application/xml", SAMPLE_AGGREGATE_XML)])
        attachments = extract_attachments(email)
        assert len(attachments) == 1
        assert attachments[0]["content"] == SAMPLE_AGGREGATE_XML
        assert attachments[0]["filename"] == "report.xml"
        assert attachments[0]["content_encoding"] is None

    def test_gzip_attachment_by_magic_bytes(self):
        compressed = gzip.compress(SAMPLE_AGGREGATE_XML)
        email = _make_mime_email([("report.xml.gz", "application/gzip", compressed)])
        attachments = extract_attachments(email)
        assert len(attachments) == 1
        assert attachments[0]["content"] == compressed
        assert attachments[0]["content_encoding"] == "gzip"

    def test_gzip_detected_by_filename(self):
        compressed = gzip.compress(SAMPLE_AGGREGATE_XML)
        email = _make_mime_email([("report.xml.gz", "application/octet-stream", compressed)])
        attachments = extract_attachments(email)
        assert len(attachments) == 1
        assert attachments[0]["content_encoding"] == "gzip"

    def test_multiple_attachments(self):
        xml2 = SAMPLE_AGGREGATE_XML.replace(b"test123", b"test456")
        email = _make_mime_email([
            ("report1.xml", "application/xml", SAMPLE_AGGREGATE_XML),
            ("report2.xml", "text/xml", xml2),
        ])
        attachments = extract_attachments(email)
        assert len(attachments) == 2
        assert attachments[0]["filename"] == "report1.xml"
        assert attachments[1]["filename"] == "report2.xml"

    def test_ignores_non_report_attachments(self):
        email = _make_mime_email([
            ("readme.txt", "text/plain", b"This is not a report"),
            ("report.xml", "application/xml", SAMPLE_AGGREGATE_XML),
            ("logo.png", "image/png", b"\x89PNG..."),
        ])
        attachments = extract_attachments(email)
        assert len(attachments) == 1
        assert attachments[0]["filename"] == "report.xml"

    def test_handles_malformed_mime(self):
        attachments = extract_attachments(b"Not a valid MIME message at all")
        assert attachments == []

    def test_nested_multipart(self):
        boundary_inner = "----=_Inner_67890"
        inner_part = (
            f'--{boundary_inner}\r\n'
            f'Content-Type: application/xml; name="report.xml"\r\n'
            f'Content-Disposition: attachment; filename="report.xml"\r\n'
            f'\r\n'
        ).encode("utf-8") + SAMPLE_AGGREGATE_XML + f'\r\n--{boundary_inner}--\r\n'.encode("utf-8")
        
        boundary_outer = "----=_Outer_12345"
        outer = (
            f'From: reporter@example.org\r\n'
            f'To: dmarc@example.com\r\n'
            f'Subject: DMARC Report\r\n'
            f'MIME-Version: 1.0\r\n'
            f'Content-Type: multipart/mixed; boundary="{boundary_outer}"\r\n'
            f'\r\n'
            f'--{boundary_outer}\r\n'
            f'Content-Type: multipart/report; boundary="{boundary_inner}"\r\n'
            f'\r\n'
        ).encode("utf-8") + inner_part + f'--{boundary_outer}--\r\n'.encode("utf-8")
        
        attachments = extract_attachments(outer)
        assert len(attachments) == 1
        assert attachments[0]["content"] == SAMPLE_AGGREGATE_XML
