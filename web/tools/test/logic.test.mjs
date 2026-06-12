import { test } from "node:test";
import assert from "node:assert/strict";
import {
  AI_BANDS, bandLabel, scanDisplay, parseCiteInputs, fingerprintRows,
  formFieldsFromTemplate, collectTemplateFields,
} from "../logic.js";

test("scanDisplay keeps the plagiarism disclaimer", () => {
  const v = scanDisplay({ plagiarism: {
    overall_match_pct: 12.4, sources: [{ url: "u", title: "t", match_pct: 7 }],
    disclaimer: "…not a legal determination…", cached: false, credits_charged: 2 } });
  assert.equal(v.plagiarism.matchPct, 12.4);
  assert.equal(v.plagiarism.sources[0].pct, 7);
  assert.match(v.plagiarism.disclaimer, /not a legal determination/);
});

test("AI detection is a three-band gauge with the confidence note, never binary", () => {
  const v = scanDisplay({ ai_detection: {
    band: "likely_ai", score: 0.83, confidence_note: "…probabilistic…", per_section: [] } });
  assert.equal(v.aiDetection.label, "Likely AI");
  assert.deepEqual(v.aiDetection.gauge, AI_BANDS);          // 3 bands
  assert.equal(v.aiDetection.gauge.length, 3);
  assert.ok(v.aiDetection.confidenceNote);                  // always present
  assert.ok(!("verdict" in v.aiDetection));                 // no YES/NO
});

test("bandLabel", () => {
  assert.equal(bandLabel("human"), "Likely human");
  assert.equal(bandLabel("weird"), "Uncertain");
});

test("parseCiteInputs splits lines and trims", () => {
  assert.deepEqual(parseCiteInputs(" 10.1/x \n\n https://e.com \n"), ["10.1/x", "https://e.com"]);
});

test("fingerprintRows formats metrics", () => {
  const rows = fingerprintRows({
    sentences: 3, words: 20, sentence_length: { mean: 6.7, distribution: { "short_<10": 2, "medium_10_20": 1, "long_>20": 0 } },
    dialogue_ratio: 0.3, adverb_density: 0.05, filter_words: { count: 2, top: ["very", "just"] } });
  const map = Object.fromEntries(rows);
  assert.equal(map["Sentences"], 3);
  assert.equal(map["Short / medium / long"], "2 / 1 / 0");
  assert.match(map["Filter words"], /very, just/);
});

test("formFieldsFromTemplate normalizes the schema", () => {
  const fields = formFieldsFromTemplate({ fields: [
    { key: "product", label: "P", required: true },
    { key: "tone", type: "select", options: ["a", "b"], default: "a" }] });
  assert.equal(fields[0].type, "text");      // default
  assert.equal(fields[0].required, true);
  assert.deepEqual(fields[1].options, ["a", "b"]);
});

test("collectTemplateFields reports missing required fields", () => {
  const fields = [{ key: "a", required: true }, { key: "b", required: false }];
  const vals = { a: "", b: "y" };
  const { values, missing } = collectTemplateFields(fields, (k) => vals[k]);
  assert.deepEqual(missing, ["a"]);
  assert.deepEqual(values, { b: "y" });
});
