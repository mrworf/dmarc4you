import { getAggregateFieldLabel } from "@/lib/aggregate-field-metadata";

export const defaultVisibleColumns = [
  "record_date",
  "domain",
  "org_name",
  "source_ip",
  "resolved_name",
  "country_code",
  "count",
  "disposition",
  "dkim_result",
  "spf_result",
  "dmarc_alignment",
  "dkim_alignment",
  "spf_alignment",
  "header_from",
];

export const dashboardColumnOptions = [
  { value: "record_date", label: getAggregateFieldLabel("record_date") },
  { value: "domain", label: getAggregateFieldLabel("domain") },
  { value: "org_name", label: getAggregateFieldLabel("org_name") },
  { value: "source_ip", label: getAggregateFieldLabel("source_ip") },
  { value: "resolved_name", label: getAggregateFieldLabel("resolved_name") },
  { value: "country_code", label: getAggregateFieldLabel("country_code") },
  { value: "country_name", label: getAggregateFieldLabel("country_name") },
  { value: "count", label: getAggregateFieldLabel("count") },
  { value: "disposition", label: getAggregateFieldLabel("disposition") },
  { value: "dkim_result", label: getAggregateFieldLabel("dkim_result") },
  { value: "spf_result", label: getAggregateFieldLabel("spf_result") },
  { value: "dmarc_alignment", label: getAggregateFieldLabel("dmarc_alignment") },
  { value: "dkim_alignment", label: getAggregateFieldLabel("dkim_alignment") },
  { value: "spf_alignment", label: getAggregateFieldLabel("spf_alignment") },
  { value: "header_from", label: getAggregateFieldLabel("header_from") },
  { value: "envelope_from", label: getAggregateFieldLabel("envelope_from") },
  { value: "envelope_to", label: getAggregateFieldLabel("envelope_to") },
  { value: "report_id", label: getAggregateFieldLabel("report_id") },
];
