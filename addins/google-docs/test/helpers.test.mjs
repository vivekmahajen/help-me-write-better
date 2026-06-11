// Tests for the pure helpers (the Google-specific Code.gs runs in Apps Script and
// isn't unit-tested here). helpers.js sets globalThis.WBDocs as a side effect.
import { test } from "node:test";
import assert from "node:assert/strict";
import "../src/helpers.js";

const { wbBuildCheckBody, wbSortSuggestions, wbSliceForRange, wbFormatSuggestion,
        wbEscapeRegex } = globalThis.WBDocs;

test("wbBuildCheckBody includes previous only when given", () => {
  assert.deepEqual(wbBuildCheckBody("a"), { text: "a" });
  assert.deepEqual(wbBuildCheckBody("a", "b"), { text: "a", previous: "b" });
});

test("wbSortSuggestions orders by severity then position", () => {
  const out = wbSortSuggestions([
    { severity: "low", range: { start: 1, end: 2 } },
    { severity: "high", range: { start: 9, end: 10 } },
    { severity: "high", range: { start: 3, end: 4 } },
  ]);
  assert.deepEqual(out.map((s) => [s.severity, s.range.start]),
    [["high", 3], ["high", 9], ["low", 1]]);
});

test("wbSliceForRange returns the substring", () => {
  assert.equal(wbSliceForRange("I will recieve it", { start: 7, end: 14 }), "recieve");
});

test("wbFormatSuggestion renders severity + message + fix", () => {
  assert.equal(
    wbFormatSuggestion({ severity: "high", message: "Possible misspelling.", replacements: ["receive"] }),
    "[high] Possible misspelling. → receive");
  assert.equal(
    wbFormatSuggestion({ severity: "low", message: "Extra space.", replacements: [" "] }),
    "[low] Extra space. →  ");
});

test("wbEscapeRegex escapes regex metacharacters", () => {
  assert.equal(wbEscapeRegex("a.b*c(d)"), "a\\.b\\*c\\(d\\)");
});
