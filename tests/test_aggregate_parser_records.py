"""Unit tests for aggregate parser record extraction."""

from backend.ingest.aggregate_parser import parse_aggregate


AGGREGATE_XML_WITH_RECORDS = b"""<?xml version="1.0" encoding="UTF-8"?>
<feedback xmlns="urn:ietf:params:xml:ns:dmarc-1">
  <report_metadata>
    <org_name>Example Org</org_name>
    <report_id>report-123</report_id>
    <date_range>
      <begin>1735689600</begin>
      <end>1735776000</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
    <adkim>r</adkim>
    <aspf>r</aspf>
    <p>reject</p>
    <pct>100</pct>
  </policy_published>
  <record>
    <row>
      <source_ip>192.0.2.1</source_ip>
      <count>10</count>
      <policy_evaluated>
        <disposition>none</disposition>
        <dkim>pass</dkim>
        <spf>pass</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
      <envelope_from>bounce.example.com</envelope_from>
      <envelope_to>recipient.example.org</envelope_to>
    </identifiers>
  </record>
  <record>
    <row>
      <source_ip>198.51.100.5</source_ip>
      <count>3</count>
      <policy_evaluated>
        <disposition>reject</disposition>
        <dkim>fail</dkim>
        <spf>fail</spf>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
    </identifiers>
  </record>
</feedback>
"""


def test_parse_aggregate_extracts_records() -> None:
    result = parse_aggregate(AGGREGATE_XML_WITH_RECORDS)
    assert result is not None
    assert result["report_id"] == "report-123"
    assert result["domain"] == "example.com"
    assert "records" in result
    assert len(result["records"]) == 2


def test_parse_aggregate_first_record_fields() -> None:
    result = parse_aggregate(AGGREGATE_XML_WITH_RECORDS)
    rec = result["records"][0]
    assert rec["source_ip"] == "192.0.2.1"
    assert rec["count"] == 10
    assert rec["disposition"] == "none"
    assert rec["dkim_result"] == "pass"
    assert rec["spf_result"] == "pass"
    assert rec["header_from"] == "example.com"
    assert rec["envelope_from"] == "bounce.example.com"
    assert rec["envelope_to"] == "recipient.example.org"


def test_parse_aggregate_second_record_fields() -> None:
    result = parse_aggregate(AGGREGATE_XML_WITH_RECORDS)
    rec = result["records"][1]
    assert rec["source_ip"] == "198.51.100.5"
    assert rec["count"] == 3
    assert rec["disposition"] == "reject"
    assert rec["dkim_result"] == "fail"
    assert rec["spf_result"] == "fail"
    assert rec["header_from"] == "example.com"
    assert rec["envelope_from"] is None
    assert rec["envelope_to"] is None


def test_parse_aggregate_no_records_returns_empty_list() -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>Org</org_name>
    <report_id>r1</report_id>
    <date_range><begin>1</begin><end>2</end></date_range>
  </report_metadata>
  <policy_published><domain>d.com</domain></policy_published>
</feedback>"""
    result = parse_aggregate(xml)
    assert result is not None
    assert result["records"] == []
