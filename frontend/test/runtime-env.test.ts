import test from "node:test";
import assert from "node:assert/strict";

import {
  buildFrontendReadyPayload,
  buildRuntimeConfigScript,
  buildServerRuntimeConfig,
  normalizeApiBaseUrl,
} from "../lib/runtime-env.ts";

test("normalizeApiBaseUrl trims one trailing slash and falls back to empty", () => {
  assert.equal(normalizeApiBaseUrl("http://127.0.0.1:8000/"), "http://127.0.0.1:8000");
  assert.equal(normalizeApiBaseUrl(undefined), "");
});

test("buildServerRuntimeConfig reads runtime env with defaults", () => {
  assert.deepEqual(
    buildServerRuntimeConfig({
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8010/",
      NEXT_PUBLIC_CSRF_COOKIE_NAME: "csrf_custom",
      NEXT_PUBLIC_REQUEST_ID_HEADER_NAME: "X-Custom-Request-ID",
    }),
    {
      apiBaseUrl: "http://127.0.0.1:8010",
      csrfCookieName: "csrf_custom",
      requestIdHeaderName: "X-Custom-Request-ID",
    },
  );

  assert.deepEqual(buildServerRuntimeConfig({}), {
    apiBaseUrl: "",
    csrfCookieName: "dmarc_csrf",
    requestIdHeaderName: "X-Request-ID",
  });
});

test("buildRuntimeConfigScript serializes the running config", () => {
  assert.equal(
    buildRuntimeConfigScript({
      apiBaseUrl: "http://127.0.0.1:8900",
      csrfCookieName: "csrf_cookie",
      requestIdHeaderName: "X-Request-ID",
    }),
    'window.__DMARC_RUNTIME_CONFIG__ = {"apiBaseUrl":"http://127.0.0.1:8900","csrfCookieName":"csrf_cookie","requestIdHeaderName":"X-Request-ID"};',
  );
});

test("buildFrontendReadyPayload reports same-origin and split-origin correctly", () => {
  assert.equal(buildFrontendReadyPayload({}).frontend.mode, "same-origin");
  assert.equal(buildFrontendReadyPayload({}).backend.apiBaseUrl, "same-origin");

  const payload = buildFrontendReadyPayload({
    NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8900/",
  });
  assert.equal(payload.frontend.mode, "split-origin");
  assert.equal(payload.backend.apiBaseUrl, "http://127.0.0.1:8900");
  assert.equal(payload.backend.readinessPath, "/api/v1/health/ready");
});
