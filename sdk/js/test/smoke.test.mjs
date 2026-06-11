// Dependency-free smoke test (node --test). Uses a mock fetch — no network.
import { test } from "node:test";
import assert from "node:assert/strict";
import { WriteBetterClient, WriteBetterError } from "../src/index.js";

function mockFetch(handler) {
  const calls = [];
  const fetch = async (url, init) => {
    calls.push({ url, init });
    const { status = 200, body = {} } = handler(url, init) || {};
    return {
      ok: status >= 200 && status < 300,
      status,
      text: async () => JSON.stringify(body),
    };
  };
  return { fetch, calls };
}

test("improve sends auth + JSON body and returns the result", async () => {
  const { fetch, calls } = mockFetch(() => ({
    body: { text: "POLISHED", model: "claude-haiku-4-5", services: ["tighten"],
            usage: { input_tokens: 5, output_tokens: 2 },
            quota: { plan: "pro", premium_cap: 300, premium_used: 0, premium_remaining: 300 } },
  }));
  const client = new WriteBetterClient({ apiKey: "wbk_test", baseUrl: "https://x/", fetch });
  const res = await client.improve({ text: "make it tighter", services: "tighten" });

  assert.equal(res.text, "POLISHED");
  const call = calls[0];
  assert.equal(call.url, "https://x/v1/improve");
  assert.equal(call.init.method, "POST");
  assert.equal(call.init.headers.Authorization, "Bearer wbk_test");
  assert.deepEqual(JSON.parse(call.init.body), { text: "make it tighter", services: "tighten" });
});

test("documents helpers unwrap envelopes", async () => {
  const { fetch, calls } = mockFetch((url, init) => {
    if (init.method === "POST") return { status: 201, body: { document: { id: 7, title: "T", content: "c" } } };
    return { body: { documents: [{ id: 7, title: "T" }] } };
  });
  const client = new WriteBetterClient({ apiKey: "k", baseUrl: "https://x", fetch });

  const doc = await client.createDocument("c", "T");
  assert.equal(doc.id, 7);
  const list = await client.listDocuments();
  assert.equal(list[0].id, 7);
  assert.equal(calls[0].url, "https://x/v1/documents");
});

test("non-2xx throws WriteBetterError with code", async () => {
  const { fetch } = mockFetch(() => ({ status: 402, body: { error: "cap reached", code: "cap_reached" } }));
  const client = new WriteBetterClient({ apiKey: "k", baseUrl: "https://x", fetch });
  await assert.rejects(
    () => client.improve({ text: "hi", services: "write" }),
    (e) => e instanceof WriteBetterError && e.status === 402 && e.code === "cap_reached",
  );
});

test("missing apiKey throws", () => {
  assert.throws(() => new WriteBetterClient({ fetch: () => {} }));
});
