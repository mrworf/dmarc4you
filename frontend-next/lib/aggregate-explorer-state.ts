import type { GroupPathPart, GroupedSearchBody, SearchRecordsBody } from "@/lib/api/types";
import { buildSearchParams, parseIntegerParam, parseStringParam } from "@/lib/url-state";

export type AggregatePageSize = number | "all";

export type AggregateExplorerState = {
  domains: string[];
  country: string;
  query: string;
  from: string;
  to: string;
  includeDmarcAlignment: string[];
  includeDkimAlignment: string[];
  includeSpfAlignment: string[];
  includeSpf: string[];
  includeDkim: string[];
  includeDisposition: string[];
  excludeDmarcAlignment: string[];
  excludeDkimAlignment: string[];
  excludeSpfAlignment: string[];
  excludeSpf: string[];
  excludeDkim: string[];
  excludeDisposition: string[];
  grouping: string[];
  pageSize: AggregatePageSize;
  page: number;
};

export type AggregateGroupingOption = {
  value: string;
  label: string;
};

export const aggregateGroupingOptions: AggregateGroupingOption[] = [
  { value: "domain", label: "Domain" },
  { value: "org_name", label: "Reporting org" },
  { value: "record_date", label: "Record date" },
  { value: "source_ip", label: "Source IP" },
  { value: "resolved_name_domain", label: "Resolved domain" },
  { value: "disposition", label: "Disposition" },
  { value: "dmarc_alignment", label: "DMARC alignment" },
  { value: "dkim_alignment", label: "DKIM alignment" },
  { value: "spf_alignment", label: "SPF alignment" },
];

export const defaultAggregateExplorerState: AggregateExplorerState = {
  domains: [],
  country: "",
  query: "",
  from: "",
  to: "",
  includeDmarcAlignment: [],
  includeDkimAlignment: [],
  includeSpfAlignment: [],
  includeSpf: [],
  includeDkim: [],
  includeDisposition: [],
  excludeDmarcAlignment: [],
  excludeDkimAlignment: [],
  excludeSpfAlignment: [],
  excludeSpf: [],
  excludeDkim: [],
  excludeDisposition: [],
  grouping: [],
  pageSize: 25,
  page: 1,
};

export const aggregatePageSizeOptions: AggregatePageSize[] = [25, 50, 100, 200, 300, "all"];

export function parseCsvParam(value: string | null): string[] {
  if (!value) {
    return [];
  }
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function buildCsvParam(values: string[]): string {
  return values.filter(Boolean).join(",");
}

export function parseAggregateExplorerState(
  searchParams: URLSearchParams,
  options: { includeDomains: boolean },
): AggregateExplorerState {
  const { includeDomains } = options;
  return {
    domains: includeDomains ? parseCsvParam(searchParams.get("domains")) : [],
    country: parseStringParam(searchParams.get("country")),
    query: parseStringParam(searchParams.get("query")),
    from: parseStringParam(searchParams.get("from")),
    to: parseStringParam(searchParams.get("to")),
    includeDmarcAlignment: parseCsvParam(searchParams.get("include_dmarc_alignment")),
    includeDkimAlignment: parseCsvParam(searchParams.get("include_dkim_alignment")),
    includeSpfAlignment: parseCsvParam(searchParams.get("include_spf_alignment")),
    includeSpf: parseCsvParam(searchParams.get("include_spf")),
    includeDkim: parseCsvParam(searchParams.get("include_dkim")),
    includeDisposition: parseCsvParam(searchParams.get("include_disposition")),
    excludeDmarcAlignment: parseCsvParam(searchParams.get("exclude_dmarc_alignment")),
    excludeDkimAlignment: parseCsvParam(searchParams.get("exclude_dkim_alignment")),
    excludeSpfAlignment: parseCsvParam(searchParams.get("exclude_spf_alignment")),
    excludeSpf: parseCsvParam(searchParams.get("exclude_spf")),
    excludeDkim: parseCsvParam(searchParams.get("exclude_dkim")),
    excludeDisposition: parseCsvParam(searchParams.get("exclude_disposition")),
    grouping: parseCsvParam(searchParams.get("grouping")).slice(0, 4),
    pageSize: parsePageSizeParam(searchParams.get("page_size")),
    page: parseIntegerParam(searchParams.get("page"), 1),
  };
}

function parsePageSizeParam(value: string | null): AggregatePageSize {
  if (value === "all") {
    return "all";
  }
  return parseIntegerParam(value, 25);
}

export function buildAggregateExplorerParams(
  state: AggregateExplorerState,
  options: { includeDomains: boolean; extraParams?: Record<string, string> },
): string {
  const { includeDomains, extraParams = {} } = options;
  return buildSearchParams({
    ...extraParams,
    domains: includeDomains ? buildCsvParam(state.domains) : "",
    country: state.country,
    query: state.query,
    from: state.from,
    to: state.to,
    include_dmarc_alignment: buildCsvParam(state.includeDmarcAlignment),
    include_dkim_alignment: buildCsvParam(state.includeDkimAlignment),
    include_spf_alignment: buildCsvParam(state.includeSpfAlignment),
    include_spf: buildCsvParam(state.includeSpf),
    include_dkim: buildCsvParam(state.includeDkim),
    include_disposition: buildCsvParam(state.includeDisposition),
    exclude_dmarc_alignment: buildCsvParam(state.excludeDmarcAlignment),
    exclude_dkim_alignment: buildCsvParam(state.excludeDkimAlignment),
    exclude_spf_alignment: buildCsvParam(state.excludeSpfAlignment),
    exclude_spf: buildCsvParam(state.excludeSpf),
    exclude_dkim: buildCsvParam(state.excludeDkim),
    exclude_disposition: buildCsvParam(state.excludeDisposition),
    grouping: buildCsvParam(state.grouping),
    page_size: state.pageSize === 25 ? "" : String(state.pageSize),
    page: state.page > 1 ? String(state.page) : "",
  });
}

export function buildAggregateSearchBody(state: AggregateExplorerState, domains: string[]): SearchRecordsBody {
  const include: Record<string, string[]> = {};
  const exclude: Record<string, string[]> = {};

  if (state.includeDmarcAlignment.length) {
    include.dmarc_alignment = state.includeDmarcAlignment;
  }
  if (state.includeDkimAlignment.length) {
    include.dkim_alignment = state.includeDkimAlignment;
  }
  if (state.includeSpfAlignment.length) {
    include.spf_alignment = state.includeSpfAlignment;
  }
  if (state.includeSpf.length) {
    include.spf_result = state.includeSpf;
  }
  if (state.includeDkim.length) {
    include.dkim_result = state.includeDkim;
  }
  if (state.includeDisposition.length) {
    include.disposition = state.includeDisposition;
  }
  if (state.excludeDmarcAlignment.length) {
    exclude.dmarc_alignment = state.excludeDmarcAlignment;
  }
  if (state.excludeDkimAlignment.length) {
    exclude.dkim_alignment = state.excludeDkimAlignment;
  }
  if (state.excludeSpfAlignment.length) {
    exclude.spf_alignment = state.excludeSpfAlignment;
  }
  if (state.excludeSpf.length) {
    exclude.spf_result = state.excludeSpf;
  }
  if (state.excludeDkim.length) {
    exclude.dkim_result = state.excludeDkim;
  }
  if (state.excludeDisposition.length) {
    exclude.disposition = state.excludeDisposition;
  }

  return {
    domains: domains.length ? domains : undefined,
    country: state.country || undefined,
    query: state.query || undefined,
    from: state.from || undefined,
    to: state.to || undefined,
    include: Object.keys(include).length ? include : undefined,
    exclude: Object.keys(exclude).length ? exclude : undefined,
    page: state.page,
    page_size: state.pageSize === "all" ? 0 : state.pageSize,
  };
}

export function buildGroupedSearchBody(
  state: AggregateExplorerState,
  domains: string[],
  options: { path?: GroupPathPart[]; page?: number; pageSize?: number } = {},
): GroupedSearchBody {
  const { path = [], page = 1, pageSize = 50 } = options;
  const body = buildAggregateSearchBody(state, domains);
  return {
    ...body,
    grouping: state.grouping,
    path,
    page,
    page_size: pageSize,
  };
}

function sortedValues(values: string[]): string[] {
  return [...values].sort((left, right) => left.localeCompare(right));
}

export function buildAggregateExplorerContextKey(state: AggregateExplorerState, domains: string[]): string {
  return JSON.stringify({
    domains: sortedValues(domains),
    country: state.country,
    query: state.query,
    from: state.from,
    to: state.to,
    includeDmarcAlignment: sortedValues(state.includeDmarcAlignment),
    includeDkimAlignment: sortedValues(state.includeDkimAlignment),
    includeSpfAlignment: sortedValues(state.includeSpfAlignment),
    includeSpf: sortedValues(state.includeSpf),
    includeDkim: sortedValues(state.includeDkim),
    includeDisposition: sortedValues(state.includeDisposition),
    excludeDmarcAlignment: sortedValues(state.excludeDmarcAlignment),
    excludeDkimAlignment: sortedValues(state.excludeDkimAlignment),
    excludeSpfAlignment: sortedValues(state.excludeSpfAlignment),
    excludeSpf: sortedValues(state.excludeSpf),
    excludeDkim: sortedValues(state.excludeDkim),
    excludeDisposition: sortedValues(state.excludeDisposition),
    grouping: state.grouping,
    pageSize: state.pageSize,
    page: state.page,
  });
}

export function getAvailableAggregateGroupingOptions(grouping: string[]): AggregateGroupingOption[] {
  return aggregateGroupingOptions.filter((option) => !grouping.includes(option.value));
}

export function getSelectedAggregateGroupingValue(grouping: string[], selectedValue: string): string {
  const availableOptions = getAvailableAggregateGroupingOptions(grouping);
  if (!availableOptions.length) {
    return "";
  }
  return availableOptions.some((option) => option.value === selectedValue)
    ? selectedValue
    : availableOptions[0].value;
}

export function toggleValue(values: string[], value: string): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function addUniqueValue(values: string[], value: string): string[] {
  if (!value || values.includes(value)) {
    return values;
  }
  return [...values, value];
}

export function removeValue(values: string[], value: string): string[] {
  return values.filter((item) => item !== value);
}

function pushParsedQueryTerm(terms: string[], value: string) {
  const trimmedValue = value.trim();
  if (trimmedValue) {
    terms.push(trimmedValue);
  }
}

export function parseQueryTerms(query: string): string[] {
  const terms: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let index = 0; index < query.length; index += 1) {
    const character = query[index];
    if (inQuotes) {
      if (character === '"') {
        if (query[index + 1] === '"') {
          current += '"';
          index += 1;
          continue;
        }
        inQuotes = false;
        continue;
      }
      current += character;
      continue;
    }

    if (/\s/.test(character)) {
      pushParsedQueryTerm(terms, current);
      current = "";
      continue;
    }

    if (character === '"' && !current) {
      inQuotes = true;
      continue;
    }

    current += character;
  }

  pushParsedQueryTerm(terms, current);
  return terms;
}

function serializeQueryTerm(term: string): string {
  return /[\s"]/.test(term) ? `"${term.replace(/"/g, '""')}"` : term;
}

export function buildQueryFromTerms(terms: string[]): string {
  const uniqueTerms: string[] = [];
  const seenTerms = new Set<string>();
  terms.forEach((term) => {
    const trimmedTerm = term.trim();
    if (!trimmedTerm || seenTerms.has(trimmedTerm)) {
      return;
    }
    seenTerms.add(trimmedTerm);
    uniqueTerms.push(trimmedTerm);
  });
  return uniqueTerms.map(serializeQueryTerm).join(" ");
}

export function removeQueryTerm(query: string, value: string): string {
  return buildQueryFromTerms(parseQueryTerms(query).filter((term) => term !== value.trim()));
}

export function appendQueryValue(query: string, value: string): string {
  const trimmedValue = value.trim();
  if (!trimmedValue) {
    return query;
  }
  const parts = parseQueryTerms(query);
  if (parts.includes(trimmedValue)) {
    return query;
  }
  return buildQueryFromTerms([...parts, trimmedValue]);
}

export function formatOptionLabel(value: string): string {
  if (!value) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}
