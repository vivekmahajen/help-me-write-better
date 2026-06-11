// Unit tests for the extension's pure logic (no DOM / chrome). core.js assigns
// globalThis.WBCore as a side effect.
import { test } from "node:test";
import assert from "node:assert/strict";
import "../src/core.js";

const { debounce, isEditableElement, getText, setText, applySuggestion,
        severityClass, SuggestionEngine } = globalThis.WBCore;

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

test("debounce fires once after the wait", async () => {
  let calls = 0;
  const d = debounce(() => calls++, 20);
  d(); d(); d();
  assert.equal(calls, 0);
  await wait(40);
  assert.equal(calls, 1);
});

test("isEditableElement recognizes editable fields only", () => {
  assert.equal(isEditableElement({ tagName: "TEXTAREA" }), true);
  assert.equal(isEditableElement({ isContentEditable: true }), true);
  assert.equal(isEditableElement({ tagName: "INPUT", type: "email" }), true);
  assert.equal(isEditableElement({ tagName: "INPUT", type: "checkbox" }), false);
  assert.equal(isEditableElement({ tagName: "TEXTAREA", readOnly: true }), false);
  assert.equal(isEditableElement({ tagName: "TEXTAREA", disabled: true }), false);
  assert.equal(isEditableElement({ tagName: "DIV" }), false);
  assert.equal(isEditableElement(null), false);
});

test("getText / setText handle value and contentEditable", () => {
  const input = { value: "hello" };
  assert.equal(getText(input), "hello");
  setText(input, "bye");
  assert.equal(input.value, "bye");

  const ce = { textContent: "rich" };
  assert.equal(getText(ce), "rich");
  setText(ce, "edited");
  assert.equal(ce.textContent, "edited");
});

test("applySuggestion replaces the exact range", () => {
  const text = "I will recieve it";
  // 'recieve' is at [7,14)
  assert.equal(applySuggestion(text, { start: 7, end: 14 }, "receive"), "I will receive it");
});

test("severityClass maps known severities", () => {
  assert.equal(severityClass("high"), "wb-sev-high");
  assert.equal(severityClass("bogus"), "wb-sev-low");
});

test("SuggestionEngine debounces, tracks previous, returns suggestions", async () => {
  const seen = [];
  const sendCheck = async (text, previous) => {
    seen.push({ text, previous });
    return { suggestions: [{ range: { start: 0, end: 3 }, message: "x" }] };
  };
  const engine = new SuggestionEngine({ sendCheck, debounceMs: 15 });

  let got = null;
  engine.onInput("teh", (s) => (got = s));
  engine.onInput("teh cat", (s) => (got = s));  // supersedes the first
  await wait(40);

  assert.equal(seen.length, 1);             // debounced to one call
  assert.equal(seen[0].text, "teh cat");
  assert.equal(seen[0].previous, null);     // first run has no previous
  assert.equal(got.length, 1);
  assert.equal(engine.previous, "teh cat"); // previous tracked for next diff
});

test("SuggestionEngine surfaces errors without throwing", async () => {
  const engine = new SuggestionEngine({
    sendCheck: async () => { throw new Error("network"); },
    debounceMs: 5,
  });
  let errSeen = null;
  engine.onInput("hi", (_s, err) => (errSeen = err));
  await wait(20);
  assert.ok(errSeen instanceof Error);
});
