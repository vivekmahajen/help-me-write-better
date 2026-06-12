// Shared config + API helper for the popup, options page, and service worker.
// Loaded via <script src="config.js"> (popup/options) and importScripts (worker).

const WB_DEFAULTS = { apiBase: "http://localhost:8000", service: "clarify" };

// A useful subset of the engine's services for quick access. Every name here
// must be a real service (the Python test cross-checks this against modes.py).
const WB_SERVICES = [
  "clarify", "correct", "tighten", "retone", "paraphrase",
  "summarize", "reply", "send-check", "dictate", "confidential",
];

async function wbConfig() {
  const got = await chrome.storage.sync.get(["apiBase", "service"]);
  return {
    apiBase: (got.apiBase || WB_DEFAULTS.apiBase).replace(/\/+$/, ""),
    service: got.service || WB_DEFAULTS.service,
  };
}

// Call the public JSON API (POST /). Throws on a non-2xx with the engine's error.
async function wbImprove(text, service, apiBase) {
  const res = await fetch(apiBase + "/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, services: [service], format: "plain" }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
  return data.text;
}
