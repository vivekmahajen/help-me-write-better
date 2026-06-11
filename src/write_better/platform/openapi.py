"""The OpenAPI 3.1 contract for the platform gateway (#5).

Single source of truth for the public API. Served at ``GET /v1/openapi.json`` and
rendered by a dependency-free viewer at ``GET /v1/docs``. The JS/TS SDK targets
this contract, and ``tests/test_openapi.py`` cross-checks it against the live
gateway routes so the spec can't drift from the implementation.
"""

from __future__ import annotations

from ..modes import MODES
from ..plans import PLANS_BY_NAME
from ..prompt import VALID_FORMATS

API_VERSION = "v1"

_SERVICE_NAMES = [m.name for m in MODES]
_PLAN_NAMES = list(PLANS_BY_NAME)

_SECURITY = [{"bearerAuth": []}, {"apiKeyHeader": []}]


def _ref(name: str) -> dict:
    return {"$ref": f"#/components/schemas/{name}"}


def _json_body(schema_name: str, required: bool = True) -> dict:
    return {
        "required": required,
        "content": {"application/json": {"schema": _ref(schema_name)}},
    }


def _json_resp(desc: str, schema_name: str | None = None) -> dict:
    out: dict = {"description": desc}
    if schema_name:
        out["content"] = {"application/json": {"schema": _ref(schema_name)}}
    return out


def _err(desc: str) -> dict:
    return _json_resp(desc, "Error")


def spec() -> dict:
    """Build the OpenAPI document (fresh dict each call)."""
    return {
        "openapi": "3.1.0",
        "info": {
            "title": "help-me-write-better API",
            "version": "1.0.0",
            "description": "Improve and format text with Claude. Authenticate with an "
                           "API key (Bearer or X-API-Key). Calls are metered and capped "
                           "per plan.",
        },
        "servers": [{"url": "/", "description": "Same-origin gateway"}],
        "security": _SECURITY,
        "paths": {
            "/v1/account": {
                "get": {
                    "operationId": "getAccount",
                    "summary": "Your account and plan",
                    "responses": {"200": _json_resp("Account", "Account"),
                                  "401": _err("Unauthorized")},
                }
            },
            "/v1/usage": {
                "get": {
                    "operationId": "getUsage",
                    "summary": "Current-period quota and usage summary",
                    "responses": {"200": _json_resp("Usage report", "UsageReport"),
                                  "401": _err("Unauthorized")},
                }
            },
            "/v1/history": {
                "get": {
                    "operationId": "getHistory",
                    "summary": "Recent requests (metadata only, no document bodies)",
                    "responses": {"200": _json_resp("History", "HistoryList"),
                                  "401": _err("Unauthorized")},
                }
            },
            "/v1/analytics": {
                "get": {
                    "operationId": "getAnalytics",
                    "summary": "Writing analytics summary + weekly insights",
                    "parameters": [{"name": "window", "in": "query", "required": False,
                                    "schema": {"type": "integer", "default": 7},
                                    "description": "Window in days (1-90)"}],
                    "responses": {"200": _json_resp("Analytics", "AnalyticsResponse"),
                                  "401": _err("Unauthorized")},
                }
            },
            "/v1/preferences": {
                "get": {
                    "operationId": "getPreferences",
                    "summary": "Synced user preferences",
                    "responses": {"200": _json_resp("Preferences", "PreferencesEnvelope"),
                                  "401": _err("Unauthorized")},
                },
                "put": {
                    "operationId": "setPreferences",
                    "summary": "Replace user preferences",
                    "requestBody": _json_body("Preferences"),
                    "responses": {"200": _json_resp("Preferences", "PreferencesEnvelope"),
                                  "401": _err("Unauthorized")},
                },
            },
            "/v1/improve": {
                "post": {
                    "operationId": "improve",
                    "summary": "Run the engine on text (metered, capped)",
                    "requestBody": _json_body("ImproveRequest"),
                    "responses": {
                        "200": _json_resp("Improved text", "ImproveResponse"),
                        "400": _err("Invalid request"),
                        "401": _err("Unauthorized"),
                        "402": _err("Plan cap reached"),
                        "502": _err("Generation failed"),
                    },
                }
            },
            "/v1/check": {
                "post": {
                    "operationId": "check",
                    "summary": "Real-time inline check (local rules, uncapped)",
                    "requestBody": _json_body("CheckRequest"),
                    "responses": {"200": _json_resp("Suggestions", "CheckResponse"),
                                  "400": _err("Invalid request"),
                                  "401": _err("Unauthorized")},
                }
            },
            "/v1/documents": {
                "get": {
                    "operationId": "listDocuments",
                    "summary": "List saved documents",
                    "responses": {"200": _json_resp("Documents", "DocumentList"),
                                  "401": _err("Unauthorized")},
                },
                "post": {
                    "operationId": "createDocument",
                    "summary": "Save a new document (creates version 1)",
                    "requestBody": _json_body("DocumentInput"),
                    "responses": {"201": _json_resp("Created", "DocumentEnvelope"),
                                  "400": _err("Invalid request"),
                                  "401": _err("Unauthorized")},
                },
            },
            "/v1/documents/{id}": {
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "integer"}}],
                "get": {
                    "operationId": "getDocument",
                    "summary": "Fetch a document (latest content)",
                    "responses": {"200": _json_resp("Document", "DocumentEnvelope"),
                                  "401": _err("Unauthorized"),
                                  "404": _err("No such document")},
                },
                "patch": {
                    "operationId": "renameDocument",
                    "summary": "Rename a document",
                    "requestBody": _json_body("RenameInput"),
                    "responses": {"200": _json_resp("Document", "DocumentEnvelope"),
                                  "401": _err("Unauthorized"),
                                  "404": _err("No such document")},
                },
                "delete": {
                    "operationId": "deleteDocument",
                    "summary": "Delete a document and its versions",
                    "responses": {"200": _json_resp("Deleted", "DeleteResult"),
                                  "401": _err("Unauthorized"),
                                  "404": _err("No such document")},
                },
            },
            "/v1/documents/{id}/versions": {
                "parameters": [{"name": "id", "in": "path", "required": True,
                                "schema": {"type": "integer"}}],
                "get": {
                    "operationId": "listVersions",
                    "summary": "List a document's versions (newest first)",
                    "responses": {"200": _json_resp("Versions", "VersionList"),
                                  "401": _err("Unauthorized"),
                                  "404": _err("No such document")},
                },
                "post": {
                    "operationId": "addVersion",
                    "summary": "Save a new version of a document",
                    "requestBody": _json_body("VersionInput"),
                    "responses": {"201": _json_resp("Updated", "DocumentEnvelope"),
                                  "400": _err("Invalid request"),
                                  "401": _err("Unauthorized"),
                                  "404": _err("No such document")},
                },
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer",
                               "description": "Authorization: Bearer <api-key>"},
                "apiKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key"},
            },
            "schemas": _schemas(),
        },
    }


def _schemas() -> dict:
    return {
        "Error": {
            "type": "object",
            "properties": {"error": {"type": "string"}, "code": {"type": "string"}},
            "required": ["error"],
        },
        "Account": {
            "type": "object",
            "properties": {"email": {"type": "string", "format": "email"},
                           "plan": {"type": "string", "enum": _PLAN_NAMES}},
            "required": ["email", "plan"],
        },
        "Quota": {
            "type": "object",
            "properties": {
                "plan": {"type": "string", "enum": _PLAN_NAMES},
                "premium_cap": {"type": "integer"},
                "premium_used": {"type": "integer"},
                "premium_remaining": {"type": "integer"},
                "period_start": {"type": "integer"},
            },
            "required": ["plan", "premium_cap", "premium_used", "premium_remaining"],
        },
        "UsageReport": {
            "type": "object",
            "properties": {
                "quota": _ref("Quota"),
                "summary": {
                    "type": "object",
                    "properties": {
                        "calls": {"type": "integer"},
                        "premium_calls": {"type": "integer"},
                        "input_tokens": {"type": "integer"},
                        "output_tokens": {"type": "integer"},
                    },
                },
            },
        },
        "Tokens": {
            "type": "object",
            "properties": {"input_tokens": {"type": "integer"},
                           "output_tokens": {"type": "integer"}},
        },
        "ImproveRequest": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The text to improve"},
                "services": {
                    "description": "One or more services (string or array)",
                    "anyOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string", "enum": _SERVICE_NAMES}},
                    ],
                },
                "format": {"type": "string", "enum": list(VALID_FORMATS), "default": "markdown"},
                "show_changes": {"type": "boolean", "default": False},
                "tone": {"type": "string"},
                "audience": {"type": "string"},
                "length": {"type": "string"},
                "reading_level": {"type": "string"},
                "language": {"type": "string"},
                "request": {"type": "string", "description": "Free-form instruction"},
                "model": {"type": "string"},
                "effort": {"type": "string", "enum": ["low", "medium", "high", "max"],
                           "default": "high"},
            },
            "required": ["text"],
        },
        "ImproveResponse": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "model": {"type": "string"},
                "services": {"type": "array", "items": {"type": "string"}},
                "usage": _ref("Tokens"),
                "quota": _ref("Quota"),
            },
            "required": ["text", "model", "services", "usage", "quota"],
        },
        "HistoryEvent": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "ts": {"type": "integer"},
                "services": {"type": "string"},
                "model": {"type": "string"},
                "premium": {"type": "integer"},
                "input_tokens": {"type": "integer"},
                "output_tokens": {"type": "integer"},
            },
        },
        "HistoryList": {
            "type": "object",
            "properties": {"history": {"type": "array", "items": _ref("HistoryEvent")}},
        },
        "Preferences": {"type": "object", "additionalProperties": True},
        "PreferencesEnvelope": {
            "type": "object", "properties": {"preferences": _ref("Preferences")},
        },
        "DocumentSummary": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "string"},
                "created_at": {"type": "integer"},
                "updated_at": {"type": "integer"},
                "versions": {"type": "integer"},
            },
        },
        "Document": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "title": {"type": "string"},
                "created_at": {"type": "integer"},
                "updated_at": {"type": "integer"},
                "content": {"type": "string"},
                "latest_version_id": {"type": ["integer", "null"]},
                "versions": {"type": "integer"},
            },
        },
        "DocumentEnvelope": {
            "type": "object", "properties": {"document": _ref("Document")},
        },
        "DocumentList": {
            "type": "object",
            "properties": {"documents": {"type": "array", "items": _ref("DocumentSummary")}},
        },
        "Version": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "content": {"type": "string"},
                           "created_at": {"type": "integer"}},
        },
        "VersionList": {
            "type": "object",
            "properties": {"versions": {"type": "array", "items": _ref("Version")}},
        },
        "DocumentInput": {
            "type": "object",
            "properties": {"title": {"type": "string", "default": "Untitled"},
                           "content": {"type": "string"}},
            "required": ["content"],
        },
        "VersionInput": {
            "type": "object",
            "properties": {"content": {"type": "string"}},
            "required": ["content"],
        },
        "RenameInput": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
        "DeleteResult": {
            "type": "object", "properties": {"deleted": {"type": "boolean"}},
        },
        "CheckRequest": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The current text to check"},
                "previous": {"type": "string",
                             "description": "Prior text; only changed sentences are re-checked"},
            },
            "required": ["text"],
        },
        "Suggestion": {
            "type": "object",
            "properties": {
                "range": {
                    "type": "object",
                    "properties": {"start": {"type": "integer"}, "end": {"type": "integer"}},
                },
                "type": {"type": "string",
                         "enum": ["spelling", "grammar", "punctuation", "style", "capitalization"]},
                "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                "message": {"type": "string"},
                "replacements": {"type": "array", "items": {"type": "string"}},
            },
        },
        "CheckResponse": {
            "type": "object",
            "properties": {
                "suggestions": {"type": "array", "items": _ref("Suggestion")},
                "count": {"type": "integer"},
            },
        },
        "AnalyticsSummary": {
            "type": "object",
            "properties": {
                "calls": {"type": "integer"},
                "words": {"type": "integer"},
                "suggestions": {"type": "integer"},
                "by_service": {"type": "object", "additionalProperties": {"type": "integer"}},
                "by_issue_type": {"type": "object", "additionalProperties": {"type": "integer"}},
                "by_day": {"type": "object"},
                "estimated_minutes_saved": {"type": "number"},
            },
        },
        "AnalyticsResponse": {
            "type": "object",
            "properties": {
                "window_days": {"type": "integer"},
                "summary": _ref("AnalyticsSummary"),
                "insights": {"type": "object"},
            },
        },
    }


# A dependency-free docs viewer (no CDN): fetches the spec and lists operations.
DOCS_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>help-me-write-better API</title>
<style>
  body{margin:0;background:#0f1221;color:#e8eaf2;
       font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  header{padding:20px 24px;border-bottom:1px solid #283049}
  h1{margin:0;font-size:19px} header p{margin:4px 0 0;color:#9aa3b8;font-size:13px}
  main{max-width:860px;margin:0 auto;padding:24px}
  .op{display:flex;gap:12px;align-items:baseline;padding:10px 12px;margin:6px 0;
      background:#171b2e;border:1px solid #283049;border-radius:8px}
  .m{font-weight:700;font-size:12px;padding:2px 8px;border-radius:6px;min-width:54px;
     text-align:center}
  .get{background:#1f3a5f;color:#9ec5ff}.post{background:#1f4d33;color:#8ff0b4}
  .put{background:#4a3b16;color:#ffd98a}.patch{background:#4a3b16;color:#ffd98a}
  .delete{background:#4d1f24;color:#ff9ea6}
  code{color:#cdd3e6}.s{color:#9aa3b8;font-size:13px;margin-left:auto;text-align:right}
</style></head><body>
<header><h1>help-me-write-better API</h1>
<p>Auth: <code>Authorization: Bearer &lt;api-key&gt;</code> (or <code>X-API-Key</code>).
Machine-readable spec: <a style="color:#6ea8fe" href="/v1/openapi.json">/v1/openapi.json</a></p></header>
<main id="ops">Loading…</main>
<script>
fetch('/v1/openapi.json').then(r=>r.json()).then(spec=>{
  const order={get:0,post:1,put:2,patch:3,delete:4};
  const rows=[];
  for(const [path,item] of Object.entries(spec.paths)){
    for(const [method,op] of Object.entries(item)){
      if(method==='parameters')continue;
      rows.push({path,method,summary:op.summary||''});
    }
  }
  rows.sort((a,b)=>a.path.localeCompare(b.path)||order[a.method]-order[b.method]);
  document.getElementById('ops').innerHTML=rows.map(r=>
    `<div class="op"><span class="m ${r.method}">${r.method.toUpperCase()}</span>`
    +`<code>${r.path}</code><span class="s">${r.summary}</span></div>`).join('');
}).catch(e=>{document.getElementById('ops').textContent='Failed to load spec: '+e;});
</script></body></html>
"""
