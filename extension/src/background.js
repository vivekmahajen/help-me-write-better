// Background service worker (MV3). Holds the API key and makes all gateway calls
// — the page/content script never sees the key. Content scripts talk to it via
// chrome.runtime.sendMessage.

const DEFAULTS = { baseUrl: "http://localhost:8000", apiKey: "", enabled: true };

async function getConfig() {
  const stored = await chrome.storage.sync.get(DEFAULTS);
  return { ...DEFAULTS, ...stored };
}

async function check(text, previous) {
  const cfg = await getConfig();
  if (!cfg.enabled) return { suggestions: [] };
  if (!cfg.apiKey) return { error: "not_configured" };

  const res = await fetch(`${cfg.baseUrl.replace(/\/+$/, "")}/v1/check`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${cfg.apiKey}`,
    },
    body: JSON.stringify(previous != null ? { text, previous } : { text }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return { error: data.error || `http_${res.status}` };
  return data;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "check") {
    check(msg.text, msg.previous).then(sendResponse);
    return true; // async response
  }
  if (msg && msg.type === "getConfig") {
    getConfig().then(sendResponse);
    return true;
  }
});
