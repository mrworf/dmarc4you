declare global {
  interface Window {
    __DMARC_RUNTIME_CONFIG__?: {
      apiBaseUrl?: string;
      csrfCookieName?: string;
      requestIdHeaderName?: string;
    };
  }
}

function readWindowConfig(): Window["__DMARC_RUNTIME_CONFIG__"] | undefined {
  if (typeof window === "undefined") {
    return undefined;
  }
  return window.__DMARC_RUNTIME_CONFIG__;
}

export function getRuntimeApiBaseUrl(): string {
  return readWindowConfig()?.apiBaseUrl?.replace(/\/$/, "") ?? process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
}

export function getRuntimeCsrfCookieName(): string {
  return readWindowConfig()?.csrfCookieName ?? process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME ?? "dmarc_csrf";
}

export function getRuntimeRequestIdHeaderName(): string {
  return readWindowConfig()?.requestIdHeaderName ?? process.env.NEXT_PUBLIC_REQUEST_ID_HEADER_NAME ?? "X-Request-ID";
}

export {};
