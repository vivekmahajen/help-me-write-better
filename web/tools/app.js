// DOM glue for the Pro Tools page. Thin client of the gateway — all view-model
// shaping lives in logic.js (unit-tested). Config (base URL + API key) persists
// in localStorage.
import {
  scanDisplay, parseCiteInputs, fingerprintRows, formFieldsFromTemplate,
  collectTemplateFields,
} from "./logic.js";

const $ = (id) => document.getElementById(id);
const cfg = JSON.parse(localStorage.getItem("wb_tools") || "{}");
$("baseUrl").value = cfg.baseUrl || "http://localhost:8000";
$("apiKey").value = cfg.apiKey || "";
const save = () => localStorage.setItem("wb_tools",
  JSON.stringify({ baseUrl: $("baseUrl").value.trim(), apiKey: $("apiKey").value.trim() }));
$("baseUrl").addEventListener("change", save);
$("apiKey").addEventListener("change", save);

async function api(method, path, body) {
  const res = await fetch($("baseUrl").value.replace(/\/+$/, "") + path, {
    method,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${$("apiKey").value.trim()}` },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}
const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));

// --- plagiarism / AI ---
$("scanBtn").addEventListener("click", async () => {
  const modes = [];
  if ($("mPlag").checked) modes.push("plagiarism");
  if ($("mAi").checked) modes.push("ai_detection");
  $("scanOut").innerHTML = "<span class='muted'>Scanning…</span>";
  try {
    const v = scanDisplay(await api("POST", "/v1/scan", { text: $("scanText").value, check: { modes } }));
    let html = "";
    if (v.plagiarism) {
      const p = v.plagiarism;
      html += `<div class="dial">${p.matchPct}% match</div>`;
      html += p.sources.map((s) => `<div class="src"><a href="${esc(s.url)}" target="_blank">${esc(s.title)}</a><span>${s.pct}%</span></div>`).join("");
      html += `<div class="disclaimer">${esc(p.disclaimer)}</div>`;
    }
    if (v.aiDetection) {
      const a = v.aiDetection;
      html += `<div class="gauge">${a.gauge.map((b) => `<span class="${b === a.band ? "on " + b : ""}">${b.replace("_", " ")}</span>`).join("")}</div>`;
      html += `<div class="muted">${a.label} · score ${a.score}</div>`;
      html += `<div class="note">${esc(a.confidenceNote)}</div>`;
    }
    $("scanOut").innerHTML = html;
  } catch (e) { $("scanOut").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
});

// --- citations ---
$("citeBtn").addEventListener("click", async () => {
  const inputs = parseCiteInputs($("citeInputs").value);
  if (!inputs.length) { $("citeOut").innerHTML = "<span class='err'>Enter at least one reference.</span>"; return; }
  $("citeOut").innerHTML = "<span class='muted'>Resolving…</span>";
  try {
    const r = await api("POST", "/v1/cite", { cite: { inputs, style: $("citeStyle").value } });
    $("citeOut").innerHTML = r.items.map((it) =>
      `<pre>${esc(it.bibliography_entry || "")}\n${esc(it.in_text || "")}</pre>` +
      (it.warnings.length ? `<div class="note">${esc(it.warnings.join("; "))}</div>` : "")).join("");
  } catch (e) { $("citeOut").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
});

// --- templates ---
let templates = [];
async function loadTemplates() {
  try {
    const r = await api("GET", "/v1/templates");
    templates = r.templates;
    $("tplCards").innerHTML = templates.map((t, i) =>
      `<div class="card" data-i="${i}"><b>${esc(t.name)}</b><span>${esc(t.category)}</span></div>`).join("");
    $("tplCards").querySelectorAll(".card").forEach((c) =>
      c.addEventListener("click", () => selectTemplate(+c.dataset.i, c)));
  } catch { /* not signed in yet */ }
}
function selectTemplate(i, card) {
  $("tplCards").querySelectorAll(".card").forEach((c) => c.classList.remove("sel"));
  card.classList.add("sel");
  const fields = formFieldsFromTemplate(templates[i]);
  $("tplForm").innerHTML = fields.map((f) => {
    const ctrl = f.options
      ? `<select id="tf_${f.key}">${f.options.map((o) => `<option ${o === f.default ? "selected" : ""}>${esc(o)}</option>`).join("")}</select>`
      : `<input type="text" id="tf_${f.key}" placeholder="${esc(f.default)}">`;
    return `<label>${esc(f.label)}${f.required ? " *" : ""}</label>${ctrl}`;
  }).join("") + `<div class="row"><button id="tplRun">Generate</button></div>`;
  $("tplRun").addEventListener("click", () => runTemplate(templates[i].id, fields));
}
async function runTemplate(id, fields) {
  const { values, missing } = collectTemplateFields(fields, (k) => ($(`tf_${k}`) || {}).value);
  if (missing.length) { $("tplOut").innerHTML = `<span class="err">Required: ${missing.join(", ")}</span>`; return; }
  $("tplOut").innerHTML = "<span class='muted'>Generating…</span>";
  try {
    const r = await api("POST", "/v1/improve", { template: id, template_fields: values });
    $("tplOut").innerHTML = (r.variants || [r.text]).map((v, n) =>
      `<div class="muted">Variant ${n + 1}</div><pre>${esc(v)}</pre>`).join("");
  } catch (e) { $("tplOut").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
}

// --- fingerprint ---
$("fpBtn").addEventListener("click", async () => {
  $("fpOut").innerHTML = "<span class='muted'>Analyzing…</span>";
  try {
    const r = await api("POST", "/v1/fingerprint", { text: $("fpText").value });
    $("fpOut").innerHTML = "<table>" + fingerprintRows(r.fingerprint)
      .map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join("") + "</table>";
  } catch (e) { $("fpOut").innerHTML = `<span class="err">${esc(e.message)}</span>`; }
});

loadTemplates();
$("apiKey").addEventListener("change", loadTemplates);
