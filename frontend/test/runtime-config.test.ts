import test from "node:test";
import assert from "node:assert/strict";

import { getRuntimeApiBaseUrl } from "../lib/runtime-config.ts";

test("getRuntimeApiBaseUrl prefers window runtime config over env", () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
  const windowStub = {
    __DMARC_RUNTIME_CONFIG__: {
      apiBaseUrl: "http://127.0.0.1:8900/",
    },
  };
  Object.defineProperty(globalThis, "window", {
    value: windowStub,
    configurable: true,
    writable: true,
  });

  assert.equal(getRuntimeApiBaseUrl(), "http://127.0.0.1:8900");

  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete (globalThis as { window?: Window }).window;
});

test("getRuntimeApiBaseUrl falls back to env when no window config exists", () => {
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8010/";
  Object.defineProperty(globalThis, "window", {
    value: undefined,
    configurable: true,
    writable: true,
  });

  assert.equal(getRuntimeApiBaseUrl(), "http://127.0.0.1:8010");

  delete process.env.NEXT_PUBLIC_API_BASE_URL;
  delete (globalThis as { window?: Window }).window;
});
