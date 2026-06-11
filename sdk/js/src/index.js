// help-me-write-better JS/TS SDK — a thin, typed client for the /v1 gateway.
// Ships as ESM JavaScript with TypeScript declarations (index.d.ts), so it works
// from both JS and TS with no build step. Targets the OpenAPI contract served at
// GET /v1/openapi.json.

export class WriteBetterError extends Error {
  constructor(status, body) {
    super((body && body.error) || `HTTP ${status}`);
    this.name = "WriteBetterError";
    this.status = status;
    this.code = body && body.code;
    this.body = body;
  }
}

export class WriteBetterClient {
  /**
   * @param {{ apiKey: string, baseUrl?: string, fetch?: typeof fetch }} options
   */
  constructor({ apiKey, baseUrl = "https://api.help-me-write-better.example", fetch: f } = {}) {
    if (!apiKey) throw new Error("apiKey is required");
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this._fetch = f || (typeof fetch !== "undefined" ? fetch : null);
    if (!this._fetch) throw new Error("no fetch available; pass options.fetch");
  }

  async _request(method, path, body) {
    const res = await this._fetch(this.baseUrl + path, {
      method,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) throw new WriteBetterError(res.status, data);
    return data;
  }

  // --- engine ---
  improve(request) { return this._request("POST", "/v1/improve", request); }

  // --- real-time inline check ---
  check(text, previous) {
    const body = previous !== undefined ? { text, previous } : { text };
    return this._request("POST", "/v1/check", body);
  }

  // --- account / usage / history / preferences ---
  getAccount() { return this._request("GET", "/v1/account"); }
  getUsage() { return this._request("GET", "/v1/usage"); }
  getHistory() { return this._request("GET", "/v1/history").then((r) => r.history); }
  getPreferences() { return this._request("GET", "/v1/preferences").then((r) => r.preferences); }
  setPreferences(prefs) {
    return this._request("PUT", "/v1/preferences", prefs).then((r) => r.preferences);
  }

  // --- documents ---
  listDocuments() { return this._request("GET", "/v1/documents").then((r) => r.documents); }
  createDocument(content, title = "Untitled") {
    return this._request("POST", "/v1/documents", { title, content }).then((r) => r.document);
  }
  getDocument(id) {
    return this._request("GET", `/v1/documents/${id}`).then((r) => r.document);
  }
  renameDocument(id, title) {
    return this._request("PATCH", `/v1/documents/${id}`, { title }).then((r) => r.document);
  }
  deleteDocument(id) {
    return this._request("DELETE", `/v1/documents/${id}`).then((r) => r.deleted);
  }
  listVersions(id) {
    return this._request("GET", `/v1/documents/${id}/versions`).then((r) => r.versions);
  }
  addVersion(id, content) {
    return this._request("POST", `/v1/documents/${id}/versions`, { content }).then((r) => r.document);
  }
}

export default WriteBetterClient;
