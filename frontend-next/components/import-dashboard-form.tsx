"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { apiClient, ApiError } from "@/lib/api/client";
import type { DashboardDetailResponse, DomainSummary, ImportDashboardBody } from "@/lib/api/types";

type ParsedImportYaml = {
  name: string;
  description: string;
  domains: string[];
};

export function ImportDashboardForm({ compact = false, domains }: { domains: DomainSummary[]; compact?: boolean }) {
  const queryClient = useQueryClient();
  const [yamlText, setYamlText] = useState("");
  const [domainRemap, setDomainRemap] = useState<Record<string, string>>({});
  const [successDashboard, setSuccessDashboard] = useState<DashboardDetailResponse | null>(null);

  const parsed = useMemo(() => parseExportYaml(yamlText), [yamlText]);
  const parseError = yamlText.trim() && !parsed ? "Invalid YAML. Expected name plus a domains list." : null;

  const importDashboard = useMutation({
    mutationFn: (body: ImportDashboardBody) => apiClient.post<DashboardDetailResponse>("/api/v1/dashboards/import", body),
    onSuccess: async (dashboard) => {
      setSuccessDashboard(dashboard);
      setYamlText("");
      setDomainRemap({});
      await queryClient.invalidateQueries({ queryKey: ["dashboards"] });
    },
  });

  const missingMappings = parsed
    ? parsed.domains.filter((domainName) => !domainRemap[domainName])
    : [];

  function handleImport() {
    if (!parsed || !parsed.domains.length) {
      return;
    }
    importDashboard.mutate({
      yaml: yamlText.trim(),
      domain_remap: domainRemap,
    });
  }

  const mutationError = importDashboard.error instanceof ApiError ? importDashboard.error.message : null;

  const content = (
    <div className="stack">
      <div>
        {!compact ? <p className="eyebrow">Import</p> : null}
        <h2 style={{ margin: "0 0 8px" }}>{compact ? "Import dashboard" : "Import a portable dashboard"}</h2>
        <p className="status-text">
          Paste exported YAML, map each source domain to a local domain, and create a new dashboard owned by the current user.
        </p>
      </div>
      <label className="field-label">
        Export YAML
        <textarea
          className="field-input monospace-block"
          onChange={(event) => {
            setYamlText(event.target.value);
            setSuccessDashboard(null);
          }}
          placeholder={"name: Deliverability\n description: Team view\n domains:\n  - example.com"}
          rows={8}
          value={yamlText}
        />
      </label>
      {parseError ? <p className="error-text">{parseError}</p> : null}
      {parsed?.domains.length ? (
        <div className="stack">
          <span className="field-label" style={{ gap: 0 }}>
            Domain remapping
          </span>
          <div className="search-state-grid">
            {parsed.domains.map((domainName) => (
              <label className="field-label" key={domainName}>
                {domainName}
                <select
                  className="field-input"
                  onChange={(event) =>
                    setDomainRemap((current) => ({
                      ...current,
                      [domainName]: event.target.value,
                    }))
                  }
                  value={domainRemap[domainName] ?? ""}
                >
                  <option value="">Select local domain</option>
                  {domains.map((domain) => (
                    <option key={domain.id} value={domain.id}>
                      {domain.name}
                    </option>
                  ))}
                </select>
              </label>
            ))}
          </div>
        </div>
      ) : null}
      {missingMappings.length ? (
        <p className="error-text">Select a local domain for: {missingMappings.join(", ")}</p>
      ) : null}
      {mutationError ? <p className="error-text">{mutationError}</p> : null}
      {successDashboard ? (
        <p className="status-text">
          Imported <strong>{successDashboard.name}</strong>. Open it from the dashboards list.
        </p>
      ) : null}
      <button
        className="button-primary"
        disabled={importDashboard.isPending || !!parseError || !!missingMappings.length || !parsed}
        onClick={handleImport}
        type="button"
      >
        {importDashboard.isPending ? "Importing..." : "Import dashboard"}
      </button>
    </div>
  );

  return compact ? content : <section className="surface-card stack">{content}</section>;
}

function parseExportYaml(text: string): ParsedImportYaml | null {
  const trimmed = text.trim();
  if (!trimmed) {
    return null;
  }

  if (trimmed.startsWith("{")) {
    try {
      const parsed = JSON.parse(trimmed) as ParsedImportYaml;
      return Array.isArray(parsed.domains) ? parsed : null;
    } catch {
      return null;
    }
  }

  let name = "";
  let description = "";
  const domains: string[] = [];
  let inDomains = false;

  for (const line of trimmed.split(/\r?\n/)) {
    const keyMatch = line.match(/^\s*(\w+):\s*(.*)$/);
    if (keyMatch) {
      inDomains = false;
      const [, key, rawValue] = keyMatch;
      const value = rawValue.trim();
      if (key === "name") {
        name = value;
      } else if (key === "description") {
        description = value;
      } else if (key === "domains") {
        inDomains = true;
      }
      continue;
    }

    const listMatch = line.match(/^\s*-\s*(.+)$/);
    if (listMatch && inDomains) {
      domains.push(listMatch[1].trim());
    }
  }

  if (!name || !domains.length) {
    return null;
  }

  return { name, description, domains };
}
