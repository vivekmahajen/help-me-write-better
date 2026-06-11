// Pure gateway client + helpers for the Word add-in. No Office.js references, so
// it's testable under node --test. taskpane.js imports this as an ES module.

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.error) || `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

export function createClient({ baseUrl, apiKey, fetch: f }) {
  const http = f || (typeof fetch !== "undefined" ? fetch : null);
  if (!http) throw new Error("no fetch available");
  const base = (baseUrl || "").replace(/\/+$/, "");

  async function request(path, body) {
    const res = await http(base + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) throw new ApiError(res.status, data);
    return data;
  }

  return {
    check: (text, previous) => request("/v1/check", previous != null ? { text, previous } : { text }),
    improve: (req) => request("/v1/improve", req),
  };
}

// The original substring a suggestion refers to — used to locate it in the Word
// document via Body.search() (Word ranges aren't plain-text char offsets).
export function sliceForRange(text, range) {
  return text.slice(range.start, range.end);
}

// Sort suggestions for display: highest severity first, then by position.
const SEV_ORDER = { high: 0, medium: 1, low: 2 };
export function sortSuggestions(suggestions) {
  return [...suggestions].sort((a, b) =>
    (SEV_ORDER[a.severity] ?? 3) - (SEV_ORDER[b.severity] ?? 3) ||
    a.range.start - b.range.start);
}
