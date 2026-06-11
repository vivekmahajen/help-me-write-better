// Word task pane glue (Office.js). Thin client of the gateway: reads the document
// or selection, calls /v1/check or /v1/improve, renders the shared suggestion
// model, and applies accepted fixes back into the document.
import { createClient, sliceForRange, sortSuggestions, ApiError } from "./api.js";

const SETTINGS_KEY = "wb_settings";

function loadSettings() {
  try {
    return JSON.parse(localStorage.getItem(SETTINGS_KEY)) || {};
  } catch {
    return {};
  }
}
function saveSettings(s) {
  localStorage.setItem(SETTINGS_KEY, JSON.stringify(s));
}

function client() {
  const { baseUrl, apiKey } = loadSettings();
  return createClient({ baseUrl: baseUrl || "http://localhost:8000", apiKey });
}

function status(msg, isError) {
  const el = document.getElementById("status");
  el.textContent = msg || "";
  el.className = isError ? "err" : "";
}

async function getText(selectionOnly) {
  return Word.run(async (context) => {
    const target = selectionOnly ? context.document.getSelection() : context.document.body;
    target.load("text");
    await context.sync();
    return target.text;
  });
}

async function applyFix(original, replacement) {
  return Word.run(async (context) => {
    const results = context.document.body.search(original, { matchCase: true });
    results.load("items");
    await context.sync();
    if (results.items.length) {
      results.items[0].insertText(replacement, Word.InsertLocation.replace);
      await context.sync();
    }
  });
}

async function replaceSelection(text) {
  return Word.run(async (context) => {
    const sel = context.document.getSelection();
    sel.insertText(text, Word.InsertLocation.replace);
    await context.sync();
  });
}

function renderSuggestions(text, suggestions) {
  const list = document.getElementById("results");
  list.innerHTML = "";
  if (!suggestions.length) {
    list.innerHTML = '<p class="muted">No issues found.</p>';
    return;
  }
  for (const s of sortSuggestions(suggestions)) {
    const original = sliceForRange(text, s.range);
    const row = document.createElement("div");
    row.className = `item sev-${s.severity}`;
    row.innerHTML = `<div class="msg">${s.message}</div>` +
      `<div class="ctx"><code>${escapeHtml(original)}</code></div>`;
    if (s.replacements && s.replacements.length) {
      const btn = document.createElement("button");
      btn.textContent = `Fix → ${s.replacements[0] || "(delete)"}`;
      btn.addEventListener("click", async () => {
        try {
          await applyFix(original, s.replacements[0] || "");
          row.remove();
        } catch (e) {
          status(`Could not apply: ${e}`, true);
        }
      });
      row.appendChild(btn);
    }
    list.appendChild(row);
  }
}

function escapeHtml(s) {
  return s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
}

async function checkDocument() {
  status("Checking…");
  try {
    const text = await getText(false);
    const { suggestions } = await client().check(text);
    renderSuggestions(text, suggestions);
    status(`${suggestions.length} suggestion(s).`);
  } catch (e) {
    status(e instanceof ApiError ? `API error: ${e.message}` : `Error: ${e}`, true);
  }
}

async function improveSelection() {
  status("Improving selection…");
  try {
    const text = await getText(true);
    if (!text.trim()) return status("Select some text first.", true);
    const service = document.getElementById("service").value;
    const result = await client().improve({ text, services: service, format: "plain" });
    await replaceSelection(result.text);
    status(`Rewrote selection (${result.model}).`);
  } catch (e) {
    status(e instanceof ApiError ? `API error: ${e.message}` : `Error: ${e}`, true);
  }
}

Office.onReady(() => {
  const s = loadSettings();
  document.getElementById("baseUrl").value = s.baseUrl || "http://localhost:8000";
  document.getElementById("apiKey").value = s.apiKey || "";
  document.getElementById("save").addEventListener("click", () => {
    saveSettings({
      baseUrl: document.getElementById("baseUrl").value.trim(),
      apiKey: document.getElementById("apiKey").value.trim(),
    });
    status("Settings saved.");
  });
  document.getElementById("check").addEventListener("click", checkDocument);
  document.getElementById("improve").addEventListener("click", improveSelection);
});
