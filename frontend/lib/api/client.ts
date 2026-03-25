import type { ApiErrorResponse } from "@/lib/api/types";

type RequestOptions = RequestInit & {
  skipCsrf?: boolean;
};

type RequestMetadata = {
  method: string;
  path: string;
  requestId: string;
  backendRequestId?: string;
};

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Array<Record<string, unknown>>;
  requestId: string;
  backendRequestId?: string;
  method: string;
  path: string;

  constructor(status: number, payload: ApiErrorResponse, metadata: RequestMetadata) {
    super(payload.error.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.error.code;
    this.details = payload.error.details;
    this.requestId = metadata.requestId;
    this.backendRequestId = metadata.backendRequestId;
    this.method = metadata.method;
    this.path = metadata.path;
  }
}

function getCookieValue(name: string): string {
  if (typeof document === "undefined") {
    return "";
  }
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : "";
}

function getApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "";
}

function getRequestIdHeaderName(): string {
  return process.env.NEXT_PUBLIC_REQUEST_ID_HEADER_NAME ?? "X-Request-ID";
}

function createRequestId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `req_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function logRequestFailure(
  message: string,
  metadata: RequestMetadata & {
    status?: number;
    error?: unknown;
  },
): void {
  console.error(message, metadata);
}

async function performRequest(path: string, options: RequestOptions = {}): Promise<{
  response: Response;
  metadata: RequestMetadata;
}> {
  const { skipCsrf, headers, ...init } = options;
  const requestHeaders = new Headers(headers);
  const method = (init.method ?? "GET").toUpperCase();
  const requestId = createRequestId();
  const requestIdHeaderName = getRequestIdHeaderName();

  requestHeaders.set(requestIdHeaderName, requestId);

  if (!skipCsrf && method !== "GET" && method !== "HEAD" && method !== "OPTIONS") {
    const csrf = getCookieValue(process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME ?? "dmarc_csrf");
    if (csrf) {
      requestHeaders.set("X-CSRF-Token", csrf);
    }
  }

  if (!requestHeaders.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
    requestHeaders.set("Content-Type", "application/json");
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      credentials: "include",
      headers: requestHeaders,
    });
    return {
      response,
      metadata: {
        method,
        path,
        requestId,
        backendRequestId: response.headers.get(requestIdHeaderName) ?? undefined,
      },
    };
  } catch (error) {
    logRequestFailure("[api] network request failed", {
      method,
      path,
      requestId,
      error,
    });
    throw error;
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { response, metadata } = await performRequest(path, options);

  if (!response.ok) {
    let payload: ApiErrorResponse = {
      error: {
        code: `http_${response.status}`,
        message: `Request failed with status ${response.status}`,
      },
      detail: `Request failed with status ${response.status}`,
    };
    try {
      payload = (await response.json()) as ApiErrorResponse;
    } catch {
      // Keep fallback payload.
    }
    logRequestFailure("[api] request failed", {
      ...metadata,
      status: response.status,
    });
    throw new ApiError(response.status, payload, metadata);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

async function requestText(path: string, options: RequestOptions = {}): Promise<string> {
  const { response, metadata } = await performRequest(path, options);

  if (!response.ok) {
    let payload: ApiErrorResponse = {
      error: {
        code: `http_${response.status}`,
        message: `Request failed with status ${response.status}`,
      },
      detail: `Request failed with status ${response.status}`,
    };
    try {
      payload = (await response.json()) as ApiErrorResponse;
    } catch {
      // Keep fallback payload.
    }
    logRequestFailure("[api] request failed", {
      ...metadata,
      status: response.status,
    });
    throw new ApiError(response.status, payload, metadata);
  }

  return response.text();
}

export const apiClient = {
  get: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "GET" }),
  getText: (path: string, options?: RequestOptions) => requestText(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: "POST",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) =>
    request<T>(path, {
      ...options,
      method: "PUT",
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>(path, { ...options, method: "DELETE" }),
};
