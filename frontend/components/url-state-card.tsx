"use client";

import { useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { buildSearchParams, parseIntegerParam } from "@/lib/url-state";

export function UrlStateCard() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [query, setQuery] = useState(searchParams.get("query") ?? "");
  const [page, setPage] = useState(parseIntegerParam(searchParams.get("page"), 1));

  const currentState = useMemo(
    () => ({
      query: searchParams.get("query") ?? "",
      page: parseIntegerParam(searchParams.get("page"), 1),
    }),
    [searchParams],
  );

  function applyState() {
    const nextParams = buildSearchParams({
      query,
      page: page > 1 ? String(page) : "",
    });
    router.replace(nextParams ? `${pathname}?${nextParams}` : pathname);
  }

  return (
    <section className="surface-card stack">
      <div>
        <p className="eyebrow">URL State</p>
        <h2 style={{ margin: "0 0 8px" }}>Shared serializer for future filters and pagination</h2>
        <p className="status-text">
          This is the pattern that will replace the current hash-based routing and filter persistence.
        </p>
      </div>
      <div className="search-state-grid">
        <label className="field-label">
          Free-text query
          <input className="field-input" onChange={(event) => setQuery(event.target.value)} value={query} />
        </label>
        <label className="field-label">
          Page
          <input
            className="field-input"
            min={1}
            onChange={(event) => setPage(parseIntegerParam(event.target.value, 1))}
            type="number"
            value={page}
          />
        </label>
      </div>
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button className="button-primary" onClick={applyState} type="button">
          Update URL
        </button>
      </div>
      <article className="placeholder-card">
        <p className="stat-label">Current parsed state</p>
        <pre className="monospace" style={{ margin: 0, whiteSpace: "pre-wrap" }}>
          {JSON.stringify(currentState, null, 2)}
        </pre>
      </article>
    </section>
  );
}
