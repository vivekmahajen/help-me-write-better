import { test } from "node:test";
import assert from "node:assert/strict";
import { createClient, sliceForRange, sortSuggestions, ApiError } from "../src/api.js";

function mockFetch(handler) {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, init });
    const { status = 200, body = {} } = handler(url, init) || {};
    return { ok: status >= 200 && status < 300, status, text: async () => JSON.stringify(body) };
  };
  return { fetch, calls };
}

test("check posts to /v1/check with auth + body", async () => {
  const { fetch, calls } = mockFetch(() => ({ body: { suggestions: [], count: 0 } }));
  const c = createClient({ baseUrl: "https://x/", apiKey: "wbk_1", fetch });
  await c.check("teh cat", "teh");
  assert.equal(calls[0].url, "https://x/v1/check");
  assert.equal(calls[0].init.headers.Authorization, "Bearer wbk_1");
  assert.deepEqual(JSON.parse(calls[0].init.body), { text: "teh cat", previous: "teh" });
});

test("improve posts to /v1/improve", async () => {
  const { fetch, calls } = mockFetch(() => ({ body: { text: "ok", model: "m", services: [], usage: {}, quota: {} } }));
  const c = createClient({ baseUrl: "https://x", apiKey: "k", fetch });
  const r = await c.improve({ text: "hi", services: "tighten" });
  assert.equal(r.text, "ok");
  assert.equal(calls[0].url, "https://x/v1/improve");
});

test("non-2xx throws ApiError", async () => {
  const { fetch } = mockFetch(() => ({ status: 402, body: { error: "cap reached", code: "cap_reached" } }));
  const c = createClient({ baseUrl: "https://x", apiKey: "k", fetch });
  await assert.rejects(() => c.improve({ text: "x", services: "write" }),
    (e) => e instanceof ApiError && e.status === 402);
});

test("sliceForRange returns the original substring", () => {
  assert.equal(sliceForRange("I will recieve it", { start: 7, end: 14 }), "recieve");
});

test("sortSuggestions orders by severity then position", () => {
  const sorted = sortSuggestions([
    { severity: "low", range: { start: 5, end: 6 } },
    { severity: "high", range: { start: 50, end: 51 } },
    { severity: "high", range: { start: 2, end: 3 } },
  ]);
  assert.deepEqual(sorted.map((s) => [s.severity, s.range.start]),
    [["high", 2], ["high", 50], ["low", 5]]);
});
