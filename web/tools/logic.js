// Pure view-model logic for the Trust-Layer tools page (plagiarism, AI detection,
// citations, templates, fingerprint). No DOM/network — shared with the unit tests.
// Enforces the product honesty rules: AI detection is always a three-band gauge
// with the confidence note attached; plagiarism always carries its disclaimer.

export const AI_BANDS = ["human", "uncertain", "likely_ai"];

export function bandLabel(band) {
  return { human: "Likely human", uncertain: "Uncertain", likely_ai: "Likely AI" }[band]
    || "Uncertain";
}

export function scanDisplay(resp) {
  const out = {};
  if (resp && resp.plagiarism) {
    const p = resp.plagiarism;
    out.plagiarism = {
      matchPct: p.overall_match_pct,
      sources: (p.sources || []).map((s) => ({ url: s.url, title: s.title, pct: s.match_pct })),
      disclaimer: p.disclaimer,            // always surfaced — not a verdict
      cached: !!p.cached,
      credits: p.credits_charged,
    };
  }
  if (resp && resp.ai_detection) {
    const a = resp.ai_detection;
    out.aiDetection = {
      band: a.band,
      label: bandLabel(a.band),
      score: a.score,
      gauge: AI_BANDS.slice(),             // three-band, never a YES/NO
      confidenceNote: a.confidence_note,   // always visible
      perSection: a.per_section || [],
    };
  }
  return out;
}

export function parseCiteInputs(text) {
  return (text || "").split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
}

export function fingerprintRows(fp) {
  if (!fp) return [];
  const sl = fp.sentence_length || {};
  const d = sl.distribution || {};
  const fw = fp.filter_words || {};
  return [
    ["Sentences", fp.sentences],
    ["Words", fp.words],
    ["Mean sentence length", sl.mean],
    ["Short / medium / long", `${d["short_<10"] || 0} / ${d["medium_10_20"] || 0} / ${d["long_>20"] || 0}`],
    ["Dialogue ratio", fp.dialogue_ratio],
    ["Adverb density", fp.adverb_density],
    ["Filter words", `${fw.count || 0}${(fw.top || []).length ? " (" + fw.top.join(", ") + ")" : ""}`],
  ];
}

export function formFieldsFromTemplate(tpl) {
  return (tpl.fields || []).map((f) => ({
    key: f.key,
    label: f.label || f.key,
    type: f.type || "text",
    required: !!f.required,
    options: f.options || null,
    default: f.default == null ? "" : f.default,
  }));
}

// Collect form values; report missing required fields (mirrors the API's 422).
export function collectTemplateFields(fields, getValue) {
  const values = {};
  const missing = [];
  for (const f of fields) {
    const v = (getValue(f.key) || "").trim();
    if (f.required && !v) missing.push(f.key);
    if (v) values[f.key] = v;
  }
  return { values, missing };
}
