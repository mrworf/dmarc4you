export type RuntimeConfig = {
  apiBaseUrl: string;
  csrfCookieName: string;
  requestIdHeaderName: string;
};

export function normalizeApiBaseUrl(value: string | undefined | null): string {
  return value?.replace(/\/$/, "") ?? "";
}

export function buildServerRuntimeConfig(
  env: Record<string, string | undefined> = process.env,
): RuntimeConfig {
  return {
    apiBaseUrl: normalizeApiBaseUrl(env["NEXT_PUBLIC_API_BASE_URL"]),
    csrfCookieName: env["NEXT_PUBLIC_CSRF_COOKIE_NAME"] ?? "dmarc_csrf",
    requestIdHeaderName: env["NEXT_PUBLIC_REQUEST_ID_HEADER_NAME"] ?? "X-Request-ID",
  };
}

export function buildRuntimeConfigScript(config: RuntimeConfig): string {
  return `window.__DMARC_RUNTIME_CONFIG__ = ${JSON.stringify(config)};`;
}

export function buildFrontendReadyPayload(
  env: Record<string, string | undefined> = process.env,
): {
  status: string;
  service: string;
  frontend: { mode: string };
  backend: { apiBaseUrl: string; readinessPath: string; sourceOfTruth: string };
  operations: { webRole: string; workerRole: string };
} {
  const runtimeConfig = buildServerRuntimeConfig(env);
  return {
    status: "ok",
    service: "frontend",
    frontend: {
      mode: runtimeConfig.apiBaseUrl ? "split-origin" : "same-origin",
    },
    backend: {
      apiBaseUrl: runtimeConfig.apiBaseUrl || "same-origin",
      readinessPath: "/api/v1/health/ready",
      sourceOfTruth: "fastapi",
    },
    operations: {
      webRole: "Next.js frontend",
      workerRole: "FastAPI background jobs and workers",
    },
  };
}
