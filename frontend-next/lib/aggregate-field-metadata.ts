export type AggregateFieldKey =
  | "record_date"
  | "domain"
  | "org_name"
  | "source_ip"
  | "resolved_name"
  | "resolved_name_domain"
  | "country_code"
  | "country_name"
  | "count"
  | "disposition"
  | "dkim_result"
  | "spf_result"
  | "dmarc_alignment"
  | "dkim_alignment"
  | "spf_alignment"
  | "header_from"
  | "envelope_from"
  | "envelope_to"
  | "report_id"
  | "records"
  | "published_policy"
  | "details";

export type AggregateFieldMetadata = {
  label: string;
  tooltip: string;
};

export const aggregateFieldMetadata: Record<AggregateFieldKey, AggregateFieldMetadata> = {
  record_date: {
    label: "Record date",
    tooltip: "Day covered by this aggregate row based on the DMARC report range.",
  },
  domain: {
    label: "Domain",
    tooltip: "Policy domain the DMARC report is about.",
  },
  org_name: {
    label: "Reporting org",
    tooltip: "Organization that generated and sent the DMARC report.",
  },
  source_ip: {
    label: "Source IP",
    tooltip: "Sending IP observed by the reporting organization.",
  },
  resolved_name: {
    label: "Resolved host (PTR)",
    tooltip: "Reverse-DNS hostname for the source IP when one is available.",
  },
  resolved_name_domain: {
    label: "Derived domain",
    tooltip: "Best-effort parent domain grouped from the resolved host.",
  },
  country_code: {
    label: "Country",
    tooltip: "Country inferred from GeoIP, not a guaranteed sender location.",
  },
  country_name: {
    label: "Country name",
    tooltip: "Country inferred from GeoIP, not a guaranteed sender location.",
  },
  count: {
    label: "Messages",
    tooltip: "Number of messages summarized by this single aggregate row.",
  },
  disposition: {
    label: "Disposition",
    tooltip: "DMARC policy action recorded for this aggregate row.",
  },
  dkim_result: {
    label: "DKIM",
    tooltip: "DKIM pass or fail result recorded in the aggregate data.",
  },
  spf_result: {
    label: "SPF",
    tooltip: "SPF pass or fail result recorded in the aggregate data.",
  },
  dmarc_alignment: {
    label: "DMARC alignment",
    tooltip: "Final DMARC-aligned outcome for the row: pass when either aligned SPF or aligned DKIM succeeds.",
  },
  dkim_alignment: {
    label: "DKIM alignment",
    tooltip: "Whether a passing DKIM signature aligned with the visible From domain under strict or relaxed policy.",
  },
  spf_alignment: {
    label: "SPF alignment",
    tooltip: "Whether the authenticated Mail From domain aligned with the visible From domain under strict or relaxed policy.",
  },
  header_from: {
    label: "Header From domain",
    tooltip: "Domain from the message Header From field used for DMARC alignment.",
  },
  envelope_from: {
    label: "Envelope From",
    tooltip: "Envelope sender value captured in the report when provided.",
  },
  envelope_to: {
    label: "Envelope To",
    tooltip: "Envelope recipient value captured in the report when provided.",
  },
  report_id: {
    label: "Report ID",
    tooltip: "Identifier assigned by the reporting organization for this DMARC report.",
  },
  records: {
    label: "Records",
    tooltip: "Number of aggregate rows in this report, not the number of messages.",
  },
  published_policy: {
    label: "Published policy",
    tooltip: "Sender DMARC policy values included in the report metadata.",
  },
  details: {
    label: "Details",
    tooltip: "Policy overrides and authentication results attached to the row.",
  },
};

export function getAggregateFieldLabel(field: AggregateFieldKey | string): string {
  return aggregateFieldMetadata[field as AggregateFieldKey]?.label ?? field;
}

export function getAggregateFieldTooltip(field: AggregateFieldKey | string): string {
  return aggregateFieldMetadata[field as AggregateFieldKey]?.tooltip ?? "";
}
