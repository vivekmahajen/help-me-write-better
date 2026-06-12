import { test } from "node:test";
import assert from "node:assert/strict";
import { debounce, applyReplacement, severityColor, CheckController } from "../src/core.js";

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

test("debounce fires once", async () => {
  let n = 0;
  const d = debounce(() => n++, 15);
  d(); d();
  await wait(35);
  assert.equal(n, 1);
});

test("applyReplacement edits the range", () => {
  assert.equal(applyReplacement("I will recieve it", { start: 7, end: 14 }, "receive"),
    "I will receive it");
});

test("severityColor maps severities", () => {
  assert.equal(severityColor("high"), "#dc2626");
  assert.equal(severityColor("unknown"), "#2563eb");
});

test("CheckController debounces, tracks previous, returns suggestions", async () => {
  const seen = [];
  const check = async (text, previous) => {
    seen.push({ text, previous });
    return { suggestions: [{ range: { start: 0, end: 3 }, message: "x" }] };
  };
  const ctl = new CheckController({ check, improve: async () => ({}), debounceMs: 15 });
  let got = null;
  ctl.onInput("teh", (s) => (got = s));
  ctl.onInput("teh cat", (s) => (got = s));
  await wait(35);
  assert.equal(seen.length, 1);
  assert.equal(seen[0].text, "teh cat");
  assert.equal(seen[0].previous, null);
  assert.equal(got.length, 1);
  assert.equal(ctl.previous, "teh cat");
});

test("rewrite calls improve and returns text", async () => {
  const ctl = new CheckController({
    check: async () => ({ suggestions: [] }),
    improve: async (req) => ({ text: `REWRITTEN:${req.services}` }),
  });
  assert.equal(await ctl.rewrite("hello", "tighten"), "REWRITTEN:tighten");
});

test("CheckController surfaces errors", async () => {
  const ctl = new CheckController({
    check: async () => { throw new Error("net"); },
    improve: async () => ({}),
    debounceMs: 5,
  });
  let err = null;
  ctl.onInput("hi", (_s, e) => (err = e));
  await wait(20);
  assert.ok(err instanceof Error);
});
