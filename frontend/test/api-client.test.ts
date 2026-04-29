import test from "node:test";
import assert from "node:assert/strict";

import { apiClient, buildApiRequestUrl } from "../lib/api/client.ts";

test("buildApiRequestUrl uses the configured api base URL", () => {
  assert.equal(buildApiRequestUrl("/api/v1/health", "http://127.0.0.1:8900"), "http://127.0.0.1:8900/api/v1/health");
  assert.equal(buildApiRequestUrl("/api/v1/health", ""), "/api/v1/health");
});

test("apiClient.get issues requests against the runtime api base URL", async () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8900";
  Object.defineProperty(globalThis, "window", {
    value: undefined,
    configurable: true,
    writable: true,
  });

  let requestedUrl = "";
  const originalFetch = globalThis.fetch;
  const originalCrypto = globalThis.crypto;
  Object.defineProperty(globalThis, "crypto", {
    value: { randomUUID: () => "req_test" } as Crypto,
    configurable: true,
  });
  globalThis.fetch = (async (input: string | URL | Request) => {
    requestedUrl = String(input);
    return new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;

  try {
    const payload = await apiClient.get<{ status: string }>("/api/v1/health");
    assert.equal(requestedUrl, "http://127.0.0.1:8900/api/v1/health");
    assert.equal(payload.status, "ok");
  } finally {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "crypto", {
      value: originalCrypto,
      configurable: true,
    });
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  }
});
