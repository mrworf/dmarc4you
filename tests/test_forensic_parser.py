"""Unit tests for forensic report parser."""

import pytest
from backend.ingest.forensic_parser import parse_forensic


MINIMAL_FORENSIC_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <version>1.0</version>
  <feedback_type>auth-failure</feedback_type>
  <report_metadata>
    <org_name>Example Org</org_name>
    <report_id>ruf-123-example.com</report_id>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
  </policy_published>
  <auth_failure>
    <source_ip>192.0.2.1</source_ip>
    <arrival_date>2026-03-01T12:00:00Z</arrival_date>
    <identifiers>
      <header_from>sender@example.com</header_from>
      <envelope_from>bounce@example.com</envelope_from>
      <envelope_to>recipient@target.com</envelope_to>
    </identifiers>
    <auth_results>
      <spf><result>fail</result></spf>
      <dkim><result>fail</result></dkim>
    </auth_results>
    <dmarc_result>fail</dmarc_result>
    <failure_type>dkim</failure_type>
  </auth_failure>
</feedback>
"""


def test_parse_forensic_minimal_valid():
    """Minimal valid forensic XML parses correctly."""
    result = parse_forensic(MINIMAL_FORENSIC_XML.encode("utf-8"))
    assert result is not None
    assert result["report_id"] == "ruf-123-example.com"
    assert result["domain"] == "example.com"
    assert result["source_ip"] == "192.0.2.1"
    assert result["org_name"] == "Example Org"
    assert result["header_from"] == "sender@example.com"
    assert result["envelope_from"] == "bounce@example.com"
    assert result["envelope_to"] == "recipient@target.com"
    assert result["spf_result"] == "fail"
    assert result["dkim_result"] == "fail"
    assert result["dmarc_result"] == "fail"
    assert result["failure_type"] == "dkim"


def test_parse_forensic_without_namespace():
    """Forensic XML without namespace parses correctly."""
    xml = """<?xml version="1.0"?>
<feedback>
  <feedback_type>auth-failure</feedback_type>
  <report_metadata>
    <org_name>Test</org_name>
    <report_id>ruf-456</report_id>
  </report_metadata>
  <policy_published>
    <domain>test.com</domain>
  </policy_published>
  <auth_failure>
    <source_ip>10.0.0.1</source_ip>
    <spf_result>softfail</spf_result>
  </auth_failure>
</feedback>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is not None
    assert result["report_id"] == "ruf-456"
    assert result["domain"] == "test.com"
    assert result["source_ip"] == "10.0.0.1"
    assert result["spf_result"] == "softfail"


def test_parse_forensic_missing_report_id():
    """Missing report_id returns None."""
    xml = """<?xml version="1.0"?>
<feedback>
  <report_metadata><org_name>Test</org_name></report_metadata>
  <policy_published><domain>test.com</domain></policy_published>
</feedback>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is None


def test_parse_forensic_missing_domain():
    """Missing domain returns None."""
    xml = """<?xml version="1.0"?>
<feedback>
  <report_metadata><report_id>ruf-789</report_id></report_metadata>
</feedback>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is None


def test_parse_forensic_invalid_xml():
    """Invalid XML returns None."""
    result = parse_forensic(b"<not valid xml")
    assert result is None


def test_parse_forensic_not_feedback_root():
    """Non-feedback root element returns None."""
    xml = """<?xml version="1.0"?>
<other_root>
  <report_metadata><report_id>ruf-999</report_id></report_metadata>
</other_root>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is None


def test_parse_forensic_oversized():
    """Oversized payload returns None."""
    huge = b"<feedback>" + (b"x" * 6 * 1024 * 1024) + b"</feedback>"
    result = parse_forensic(huge)
    assert result is None


def test_parse_forensic_with_record_wrapper():
    """Forensic XML with auth_failure inside record element parses correctly."""
    xml = """<?xml version="1.0"?>
<feedback>
  <feedback_type>failure</feedback_type>
  <report_metadata>
    <org_name>Wrapped Org</org_name>
    <report_id>ruf-wrapped</report_id>
  </report_metadata>
  <policy_published>
    <domain>wrapped.com</domain>
  </policy_published>
  <record>
    <auth_failure>
      <source_ip>203.0.113.5</source_ip>
      <header_from>from@wrapped.com</header_from>
      <failure>spf</failure>
    </auth_failure>
  </record>
</feedback>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is not None
    assert result["report_id"] == "ruf-wrapped"
    assert result["domain"] == "wrapped.com"
    assert result["source_ip"] == "203.0.113.5"
    assert result["header_from"] == "from@wrapped.com"
    assert result["failure_type"] == "spf"


def test_parse_forensic_arrival_time_variant():
    """arrival_time field (variant of arrival_date) is recognized."""
    xml = """<?xml version="1.0"?>
<feedback>
  <report_metadata><report_id>ruf-time</report_id></report_metadata>
  <policy_published><domain>time.com</domain></policy_published>
  <auth_failure>
    <arrival_time>2026-03-02T10:00:00Z</arrival_time>
  </auth_failure>
</feedback>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is not None
    assert result["arrival_time"] == "2026-03-02T10:00:00Z"


def test_parse_forensic_empty_optional_fields():
    """Missing optional fields are None, not errors."""
    xml = """<?xml version="1.0"?>
<feedback>
  <report_metadata><report_id>ruf-minimal</report_id></report_metadata>
  <policy_published><domain>minimal.com</domain></policy_published>
</feedback>
"""
    result = parse_forensic(xml.encode("utf-8"))
    assert result is not None
    assert result["report_id"] == "ruf-minimal"
    assert result["domain"] == "minimal.com"
    assert result["source_ip"] is None
    assert result["arrival_time"] is None
    assert result["header_from"] is None
    assert result["spf_result"] is None
    assert result["dkim_result"] is None
    assert result["dmarc_result"] is None
    assert result["failure_type"] is None
