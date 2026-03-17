import tempfile

from backend.auth.bootstrap import ensure_bootstrap_admin
from backend.config.schema import Config
from backend.jobs.runner import run_one_job
from backend.services.domain_service import create_domain
from backend.services.ingest_service import create_ingest_job
from backend.storage.sqlite import get_connection, run_migrations


AGGREGATE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feedback>
  <report_metadata>
    <org_name>Example Org</org_name>
    <email>dmarc@example.net</email>
    <extra_contact_info>mailto:postmaster@example.net</extra_contact_info>
    <report_id>rfc-rich-report</report_id>
    <error>sample-error</error>
    <date_range>
      <begin>1735689600</begin>
      <end>1735776000</end>
    </date_range>
  </report_metadata>
  <policy_published>
    <domain>example.com</domain>
    <adkim>s</adkim>
    <aspf>r</aspf>
    <p>reject</p>
    <sp>quarantine</sp>
    <pct>75</pct>
    <fo>1:d</fo>
  </policy_published>
  <record>
    <row>
      <source_ip>192.0.2.10</source_ip>
      <count>4</count>
      <policy_evaluated>
        <disposition>none</disposition>
        <dkim>pass</dkim>
        <spf>fail</spf>
        <reason>
          <type>forwarded</type>
          <comment>mailing list</comment>
        </reason>
      </policy_evaluated>
    </row>
    <identifiers>
      <header_from>example.com</header_from>
      <envelope_from>bounce.example.com</envelope_from>
    </identifiers>
    <auth_results>
      <dkim>
        <domain>example.com</domain>
        <selector>mail</selector>
        <result>pass</result>
      </dkim>
      <spf>
        <domain>bounce.example.com</domain>
        <scope>mfrom</scope>
        <result>fail</result>
      </spf>
    </auth_results>
  </record>
</feedback>
"""


def test_run_one_job_persists_rich_aggregate_fields(monkeypatch) -> None:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    run_migrations(handle.name)
    ensure_bootstrap_admin(handle.name)
    config = Config(
        database_path=handle.name,
        log_level="INFO",
        session_secret="secret",
        session_cookie_name="session",
        session_max_age_days=7,
    )
    conn = get_connection(handle.name)
    admin_id = conn.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()[0]
    conn.close()
    status, _ = create_domain(config, "example.com", admin_id, "super-admin")
    assert status == "ok"

    class _FakeGeoProvider:
        def lookup_country(self, ip_text: str | None):
            class Result:
                country_code = "US"
                country_name = "United States"
                provider = "dbip-lite-country"
            return Result()

    monkeypatch.setattr("backend.jobs.runner.resolve_ip", lambda config, ip: ("mail.example.net", "example.net"))
    monkeypatch.setattr("backend.jobs.runner.build_geoip_provider", lambda config: _FakeGeoProvider())

    create_ingest_job(
        config,
        {"reports": [{"content_type": "application/xml", "content": AGGREGATE_XML}]},
        "user",
        actor_user_id=admin_id,
    )
    assert run_one_job(config) is True

    conn = get_connection(handle.name)
    report = conn.execute(
        """SELECT contact_email, extra_contact_info, error_messages_json, adkim, aspf, policy_p, policy_sp, policy_pct, policy_fo
           FROM aggregate_reports"""
    ).fetchone()
    record = conn.execute(
        """SELECT resolved_name, resolved_name_domain, country_code, country_name, geo_provider, dkim_alignment, spf_alignment, dmarc_alignment
           FROM aggregate_report_records"""
    ).fetchone()
    override = conn.execute(
        "SELECT reason_type, comment FROM aggregate_record_policy_overrides"
    ).fetchone()
    auth_rows = conn.execute(
        "SELECT auth_method, domain, selector, scope, result FROM aggregate_record_auth_results ORDER BY auth_method"
    ).fetchall()
    conn.close()

    assert report == (
        "dmarc@example.net",
        "mailto:postmaster@example.net",
        '["sample-error"]',
        "s",
        "r",
        "reject",
        "quarantine",
        75,
        "1:d",
    )
    assert record == ("mail.example.net", "example.net", "US", "United States", "dbip-lite-country", "strict", "none", "pass")
    assert override == ("forwarded", "mailing list")
    assert auth_rows == [
        ("dkim", "example.com", "mail", None, "pass"),
        ("spf", "bounce.example.com", None, "mfrom", "fail"),
    ]
