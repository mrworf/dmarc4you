export type UserRole = "super-admin" | "admin" | "manager" | "viewer";

export type UserSummary = {
  id: string;
  username: string;
  role: UserRole;
  full_name: string | null;
  email: string | null;
};

export type UpdateProfileBody = {
  full_name?: string | null;
  email?: string | null;
};

export type AuthMeResponse = {
  user: UserSummary;
  all_domains: boolean;
  domain_ids: string[];
  password_change_required: boolean;
};

export type AuthLoginBody = {
  username: string;
  password: string;
};

export type AuthLoginResponse = {
  user: UserSummary;
  password_change_required: boolean;
};

export type UpdatePasswordBody = {
  current_password: string;
  new_password: string;
};

export type UpdatePasswordResponse = {
  password_changed: boolean;
  reauth_required: boolean;
};

export type DomainSummary = {
  id: string;
  name: string;
  status: string;
  created_at: string;
  archived_at?: string | null;
  retention_days?: number | null;
  retention_delete_at?: string | null;
  retention_paused?: number | boolean | null;
  retention_remaining_seconds?: number | null;
  monitoring_enabled?: number | boolean | null;
  monitoring_last_checked_at?: string | null;
  monitoring_next_check_at?: string | null;
  monitoring_last_change_at?: string | null;
  monitoring_failure_active?: number | boolean | null;
  monitoring_last_failure_at?: string | null;
  monitoring_last_failure_summary?: string | null;
  latest_maintenance_job?: DomainMaintenanceJobSummary | null;
};

export type DomainsResponse = {
  domains: DomainSummary[];
};

export type CreateDomainBody = {
  name: string;
};

export type ArchiveDomainBody = {
  retention_days?: number | null;
};

export type SetDomainRetentionBody = {
  retention_days: number;
};

export type PauseDomainRetentionBody = {
  reason?: string | null;
};

export type DomainMutationResponse = {
  domain: DomainSummary;
};

export type DomainMaintenanceJobSummary = {
  job_id: string;
  domain_id: string;
  domain_name: string;
  action: string;
  actor_user_id?: string | null;
  actor_api_key_id?: string | null;
  state: string;
  submitted_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  reports_scanned: number;
  reports_skipped: number;
  records_updated: number;
  last_error?: string | null;
  summary?: string | null;
};

export type DomainMaintenanceJobMutationResponse = {
  job: DomainMaintenanceJobSummary;
};

export type DomainMaintenanceJobListResponse = {
  jobs: DomainMaintenanceJobSummary[];
};

export type DomainMonitoringRecordState = {
  status: string;
  host: string;
  raw_value?: string | null;
  parsed?: Record<string, unknown> | null;
  explanation?: string | null;
  summary?: string | null;
  ttl_seconds?: number | null;
  details?: DomainMonitoringDetailItem[];
};

export type DomainMonitoringDetailItem = {
  label: string;
  values: string[];
  value_type?: "text" | "email" | string;
  display?: "inline" | "list" | string;
};

export type DomainMonitoringCurrentState = {
  checked_at: string;
  ttl_seconds?: number | null;
  error_summary?: string | null;
  dmarc: DomainMonitoringRecordState;
  spf: DomainMonitoringRecordState;
  dkim: DomainMonitoringRecordState[];
};

export type DomainMonitoringHistoryEntry = {
  id: string;
  changed_at: string;
  summary: string;
  overall_direction: "improved" | "degraded" | "neutral";
  changes: Array<Record<string, unknown>>;
  previous_state?: Record<string, unknown> | null;
  current_state: Record<string, unknown>;
};

export type DomainMonitoringResponse = {
  domain: DomainSummary;
  dkim_selectors: string[];
  current_state?: DomainMonitoringCurrentState | null;
  history: DomainMonitoringHistoryEntry[];
};

export type DomainMonitoringTimelineResponse = {
  domain: DomainSummary;
  last_checked_at?: string | null;
  history: DomainMonitoringHistoryEntry[];
};

export type UpdateDomainMonitoringBody = {
  enabled: boolean;
  dkim_selectors: string[];
};

export type TriggerDomainMonitoringCheckResponse = {
  state: "queued" | "suppressed_recently";
};

export type DashboardSummary = {
  id: string;
  name: string;
  description: string;
  owner_user_id: string;
  owner?: UserSummary | null;
  created_at: string;
  updated_at: string;
  domain_ids: string[];
  domain_names?: string[] | null;
  visible_columns: string[];
  chart_y_axis: "message_count" | "row_count" | "report_count";
};

export type DashboardsResponse = {
  dashboards: DashboardSummary[];
};

export type CreateDashboardBody = {
  name: string;
  description?: string;
  domain_ids: string[];
  visible_columns?: string[];
  chart_y_axis?: "message_count" | "row_count" | "report_count";
};

export type UpdateDashboardBody = {
  name?: string;
  description?: string;
  domain_ids?: string[];
  visible_columns?: string[];
  chart_y_axis?: "message_count" | "row_count" | "report_count";
};

export type DashboardDetailResponse = DashboardSummary;

export type DashboardShareSummary = {
  user_id: string;
  username: string;
  access_level: "viewer" | "manager";
  granted_by_user_id: string;
  granted_at: string;
};

export type DashboardSharesResponse = {
  shares: DashboardShareSummary[];
};

export type DashboardValidateUpdateImpactedUser = {
  user_id: string;
  username: string;
  access_level: "viewer" | "manager";
};

export type DashboardValidateUpdateResponse = {
  valid: boolean;
  impacted_users: DashboardValidateUpdateImpactedUser[];
};

export type ShareDashboardBody = {
  user_id: string;
  access_level: "viewer" | "manager";
};

export type TransferDashboardOwnershipBody = {
  user_id: string;
};

export type ImportDashboardBody = {
  yaml: string;
  domain_remap: Record<string, string>;
};

export type IngestReportEnvelopeItem = {
  content_type: string;
  content_encoding: string;
  content_transfer_encoding: string;
  content: string;
};

export type ReportsIngestBody = {
  source: string;
  reports: IngestReportEnvelopeItem[];
};

export type ReportsIngestResponse = {
  job_id: string;
  state: string;
};

export type IngestJobSummary = {
  job_id: string;
  state: string;
  submitted_at?: string | null;
};

export type IngestJobsResponse = {
  jobs: IngestJobSummary[];
};

export type IngestJobItem = {
  item_id?: string;
  job_id?: string;
  sequence_no?: number;
  report_type_detected?: string;
  domain_detected?: string;
  status?: string;
  status_reason?: string;
  normalized_report_id?: string | null;
  normalized_report_kind?: "aggregate" | "forensic" | null;
};

export type IngestJobDetailResponse = {
  job_id: string;
  actor_type?: string;
  actor_user_id?: string | null;
  state: string;
  submitted_at?: string;
  started_at?: string | null;
  completed_at?: string | null;
  last_error?: string | null;
  retry_count?: number;
  accepted_count?: number;
  duplicate_count?: number;
  invalid_count?: number;
  rejected_count?: number;
  items?: IngestJobItem[];
};

export type CreateUserBody = {
  username: string;
  role: UserRole;
  full_name?: string | null;
  email?: string | null;
};

export type UpdateUserBody = {
  username?: string;
  role?: UserRole;
  full_name?: string | null;
  email?: string | null;
};

export type ListedUserSummary = UserSummary & {
  created_at?: string;
  created_by_user_id?: string;
  domain_ids?: string[];
};

export type UsersResponse = {
  users: ListedUserSummary[];
};

export type UserDetailResponse = {
  user: ListedUserSummary;
};

export type CreateUserResponse = {
  user: ListedUserSummary;
  password: string;
};

export type ResetUserPasswordResponse = {
  password: string;
};

export type AssignUserDomainsBody = {
  domain_ids: string[];
};

export type ApiKeySummary = {
  id: string;
  nickname: string;
  description: string;
  domain_ids: string[];
  domain_names: string[];
  scopes: string[];
  created_at: string;
};

export type ApiKeysResponse = {
  keys: ApiKeySummary[];
};

export type CreateApiKeyBody = {
  nickname: string;
  description?: string;
  domain_ids: string[];
  scopes: string[];
};

export type CreateApiKeyResponse = {
  id: string;
  nickname: string;
  key: string;
};

export type UpdateApiKeyBody = {
  nickname: string;
  description?: string;
  scopes: string[];
};

export type UpdateApiKeyResponse = {
  key: ApiKeySummary;
};

export type AuditEvent = {
  id: string;
  timestamp: string;
  actor_type: string | null;
  actor_user_id: string | null;
  action_type: string;
  outcome: string | null;
  source_ip: string | null;
  user_agent: string | null;
  summary: string;
};

export type AuditEventsResponse = {
  events: AuditEvent[];
  available_action_types: string[];
};

export type SearchRecordsBody = {
  domains?: string[];
  from?: string | number;
  to?: string | number;
  include?: Record<string, string[]>;
  exclude?: Record<string, string[]>;
  country?: string;
  query?: string;
  group_by?: string;
  page?: number;
  page_size?: number;
};

export type SearchTimeSeriesBody = {
  domains?: string[];
  from?: string | number;
  to?: string | number;
  include?: Record<string, string[]>;
  exclude?: Record<string, string[]>;
  country?: string;
  query?: string;
  y_axis?: "message_count" | "row_count" | "report_count";
};

export type SearchTimeSeriesBucket = {
  date: string;
  spf: {
    pass: number;
    fail: number;
    unknown: number;
  };
  dkim: {
    pass: number;
    fail: number;
    unknown: number;
  };
  dmarc: {
    pass: number;
    fail: number;
    unknown: number;
  };
};

export type SearchTimeSeriesResponse = {
  buckets: SearchTimeSeriesBucket[];
  series_order: string[];
  y_axis: "message_count" | "row_count" | "report_count";
};

export type GroupPathPart = {
  field: string;
  value: string;
};

export type GroupedSearchBody = {
  domains?: string[];
  from?: string | number;
  to?: string | number;
  include?: Record<string, string[]>;
  exclude?: Record<string, string[]>;
  country?: string;
  query?: string;
  grouping: string[];
  path?: GroupPathPart[];
  page?: number;
  page_size?: number;
};

export type AggregateSearchResult = {
  id: string;
  aggregate_report_id: string;
  source_ip: string | null;
  resolved_name: string | null;
  resolved_name_domain: string | null;
  country_code: string | null;
  country_name: string | null;
  geo_provider: string | null;
  count: number;
  disposition: string | null;
  dkim_result: string | null;
  spf_result: string | null;
  dkim_alignment: string | null;
  spf_alignment: string | null;
  dmarc_alignment: string | null;
  header_from: string | null;
  envelope_from: string | null;
  envelope_to: string | null;
  domain: string;
  report_id: string;
  org_name: string | null;
  date_begin: number;
  date_end: number;
  record_date: string | null;
};

export type GroupedSearchResult = {
  group_by: string;
  group_value: string;
  group_label: string;
  row_count: number;
  report_count: number;
  count: number;
  date_begin: number | null;
  date_end: number | null;
  record_date: string | null;
};

export type GroupedSearchNode = {
  type: "group";
  field: string;
  value: string;
  label: string;
  path: GroupPathPart[];
  row_count: number;
  report_count: number;
  message_count: number;
  first_record_date: string | null;
  last_record_date: string | null;
  dmarc_alignment_summary: {
    pass: number;
    fail: number;
    unknown: number;
  };
  disposition_summary: {
    none: number;
    quarantine: number;
    reject: number;
  };
  has_children: boolean;
};

export type GroupedSearchLeafRow = AggregateSearchResult & {
  type: "row";
};

export type GroupedSearchResponse = {
  items: Array<GroupedSearchNode | GroupedSearchLeafRow>;
  total: number;
  page: number;
  page_size: number;
  grouping: string[];
  path: GroupPathPart[];
  level_kind: "group" | "row";
};

export type SearchRecordsResponse = {
  items: Array<AggregateSearchResult | GroupedSearchResult>;
  total: number;
  page: number;
  page_size: number;
  group_by?: string | null;
};

export type ForensicReportSummary = {
  id: string;
  report_id: string;
  domain: string;
  source_ip: string | null;
  resolved_name: string | null;
  resolved_name_domain: string | null;
  country_code: string | null;
  country_name: string | null;
  geo_provider: string | null;
  arrival_time: string | null;
  org_name: string | null;
  header_from: string | null;
  envelope_from: string | null;
  envelope_to: string | null;
  spf_result: string | null;
  dkim_result: string | null;
  dmarc_result: string | null;
  failure_type: string | null;
  created_at: string;
};

export type ForensicReportsResponse = {
  items: ForensicReportSummary[];
  total: number;
  page: number;
  page_size: number;
};

export type AggregateReportDetailRecord = {
  id: string;
  source_ip: string | null;
  resolved_name: string | null;
  resolved_name_domain: string | null;
  country_code: string | null;
  country_name: string | null;
  geo_provider: string | null;
  count: number;
  disposition: string | null;
  dkim_result: string | null;
  spf_result: string | null;
  dkim_alignment: string | null;
  spf_alignment: string | null;
  dmarc_alignment: string | null;
  header_from: string | null;
  envelope_from: string | null;
  envelope_to: string | null;
  policy_overrides: Array<{
    type: string | null;
    comment: string | null;
  }>;
  auth_results: Array<{
    auth_method: string;
    domain: string | null;
    selector: string | null;
    scope: string | null;
    result: string | null;
    human_result: string | null;
  }>;
};

export type AggregateReportDetailResponse = {
  id: string;
  report_id: string;
  org_name: string | null;
  domain: string;
  date_begin: number;
  date_end: number;
  created_at: string;
  contact_email?: string | null;
  extra_contact_info?: string | null;
  error_messages?: string[];
  published_policy?: {
    adkim?: string | null;
    aspf?: string | null;
    p?: string | null;
    sp?: string | null;
    pct?: number | null;
    fo?: string | null;
  };
  records: AggregateReportDetailRecord[];
};

export type ForensicReportDetailResponse = {
  id: string;
  report_id: string;
  domain: string;
  source_ip: string | null;
  resolved_name: string | null;
  resolved_name_domain: string | null;
  country_code: string | null;
  country_name: string | null;
  geo_provider: string | null;
  arrival_time: string | null;
  org_name: string | null;
  header_from: string | null;
  envelope_from: string | null;
  envelope_to: string | null;
  spf_result: string | null;
  dkim_result: string | null;
  dmarc_result: string | null;
  failure_type: string | null;
  created_at: string;
};

export type ApiErrorDetail = {
  code: string;
  message: string;
  details?: Array<Record<string, unknown>>;
};

export type ApiErrorResponse = {
  error: ApiErrorDetail;
  detail: string;
  details?: Array<Record<string, unknown>>;
};
