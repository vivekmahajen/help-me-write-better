"""The signed-in account settings surface (browser, session-authed).

A single page at ``GET /account`` with two management panels backed by the same
store the gateway uses:

* **Personal dictionary** (#5) — words the engine must never flag or change.
* **Voice profile** (#4) — a writing sample the engine matches ("sounds like me").

The page's JavaScript calls same-origin JSON endpoints under ``/account/*`` that
authenticate via the **session cookie** (not an API key). Those cookies are
``SameSite=Lax``, so cross-site state-changing requests don't carry them — the
mutating POST/PUT/DELETE handlers below are CSRF-safe on that basis.

The gateway's ``/v1/dictionary`` and ``/v1/voice`` (API-key authed) remain the
programmatic path; this surface is the human one over the very same data.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs

from ..engine import Request, has_api_key, improve as engine_improve
from ..templating import MissingFields, get_template, list_templates, validate_and_render
from ..voice import build_profile
from .webauth import current_user


def _json(start_response, status, payload):
    body = json.dumps(payload).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def _html(start_response, page, status="200 OK"):
    body = page.encode("utf-8")
    start_response(status, [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ])
    return [body]


def _read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    raw = environ["wsgi.input"].read(length) if length > 0 else b""
    if not raw:
        return {}, None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None, "request body must be valid JSON"
    return (data, None) if isinstance(data, dict) else (None, "body must be an object")


def make_account(store, engine=engine_improve):
    """A WSGI app mounted at ``/account`` (see ``platform/wsgi.py``)."""

    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        parts = [p for p in environ.get("PATH_INFO", "/").split("/") if p]
        rest = parts[1:]  # drop "account"

        user = current_user(store, environ)

        # The page itself: a sign-in nudge when logged out, the settings UI when in.
        if rest == []:
            if not user:
                return _html(start_response, _SIGNIN_PAGE)
            return _html(start_response, ACCOUNT_PAGE)

        # Everything else is JSON and requires a session.
        if not user:
            return _json(start_response, "401 Unauthorized",
                         {"error": "not signed in", "code": "unauthorized"})
        uid = user["id"]

        # Template gallery (session-authed): list the library + run one through
        # the engine, so signed-in users can test templates in the browser with
        # no API key. Injectable engine for offline tests.
        if rest == ["templates"] and method == "GET":
            category = (parse_qs(environ.get("QUERY_STRING", "")).get("category") or [None])[0]
            return _json(start_response, "200 OK", {"templates": list_templates(category)})

        if rest == ["templates", "run"] and method == "POST":
            data, err = _read_json(environ)
            if err:
                return _json(start_response, "400 Bad Request", {"error": err})
            tpl = get_template(data.get("template") or "")
            if tpl is None:
                return _json(start_response, "422 Unprocessable Entity", {
                    "error": f"unknown template {data.get('template')!r}",
                    "code": "unknown_template"})
            try:
                text = validate_and_render(tpl, data.get("fields") or {})
            except MissingFields as exc:
                return _json(start_response, "422 Unprocessable Entity", {
                    "error": str(exc), "code": "missing_fields",
                    "missing": exc.missing, "fields": list(tpl.fields)})
            if not has_api_key():
                return _json(start_response, "503 Service Unavailable",
                             {"error": "the engine is not configured on this server"})
            try:
                result = engine(Request(
                    text=text, services=[tpl.defaults.get("service", "write")],
                    output_format=tpl.defaults.get("format", "markdown")))
            except Exception as exc:  # surface engine errors cleanly
                return _json(start_response, "502 Bad Gateway",
                             {"error": f"generation failed: {exc}"})
            return _json(start_response, "200 OK",
                         {"text": result.text, "model": result.model, "template": tpl.id})

        if rest == ["dictionary"]:
            if method == "GET":
                return _json(start_response, "200 OK", {"terms": store.list_dictionary(uid)})
            if method in ("POST", "DELETE"):
                data, err = _read_json(environ)
                if err:
                    return _json(start_response, "400 Bad Request", {"error": err})
                term = (data.get("term") or "").strip()
                if not term:
                    return _json(start_response, "400 Bad Request",
                                 {"error": "'term' is required"})
                if method == "POST":
                    store.add_dictionary_term(uid, term)
                    return _json(start_response, "201 Created",
                                 {"terms": store.list_dictionary(uid)})
                if not store.remove_dictionary_term(uid, term):
                    return _json(start_response, "404 Not Found",
                                 {"error": f"term {term!r} not in dictionary"})
                return _json(start_response, "200 OK", {"terms": store.list_dictionary(uid)})
            return _json(start_response, "405 Method Not Allowed",
                         {"error": "use GET, POST, or DELETE"})

        if rest == ["voice"]:
            if method == "GET":
                vp = store.get_voice_profile(uid)
                return _json(start_response, "200 OK",
                             {"voice": build_profile(vp["samples"]) if vp else None})
            if method in ("PUT", "POST"):
                data, err = _read_json(environ)
                if err:
                    return _json(start_response, "400 Bad Request", {"error": err})
                samples = (data.get("samples") or "").strip()
                if not samples:
                    return _json(start_response, "400 Bad Request",
                                 {"error": "'samples' is required"})
                store.set_voice_profile(uid, samples)
                return _json(start_response, "201 Created", {"voice": build_profile(samples)})
            if method == "DELETE":
                store.clear_voice_profile(uid)
                return _json(start_response, "200 OK", {"voice": None})
            return _json(start_response, "405 Method Not Allowed",
                         {"error": "use GET, PUT, or DELETE"})

        return _json(start_response, "404 Not Found", {"error": "no such endpoint"})

    return app


_SIGNIN_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Account — Help Me Write Better</title>
<style>
  body { margin:0; height:100vh; display:grid; place-items:center; background:#0f1221;
         color:#e8eaf2; font:15px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  a { color:#6ea8fe; }
</style></head>
<body><div style="text-align:center">
  <h1>Your account</h1>
  <p>Please <a href="/auth/login">sign in</a> to manage your dictionary and voice profile.</p>
</div></body></html>
"""


ACCOUNT_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Account — Help Me Write Better</title>
<style>
  :root { --bg:#0f1221; --panel:#171b2e; --ink:#e8eaf2; --muted:#9aa3b8;
          --accent:#6ea8fe; --line:#283049; --err:#e06c75; --ok:#3fb37f; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--ink);
         font:15px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; }
  header { padding:18px 24px; border-bottom:1px solid var(--line); display:flex;
           align-items:center; gap:16px; }
  header h1 { margin:0; font-size:18px; } header .sp { flex:1; }
  header a { color:var(--accent); font-size:14px; text-decoration:none; }
  main { max-width:860px; margin:0 auto; padding:24px; display:grid; gap:20px;
         grid-template-columns:1fr 1fr; }
  @media (max-width:760px){ main { grid-template-columns:1fr; } }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:16px; }
  .panel h2 { margin:0 0 4px; font-size:15px; }
  .panel p.hint { margin:0 0 12px; color:var(--muted); font-size:13px; }
  input, textarea { width:100%; background:#0c0f1c; color:var(--ink);
          border:1px solid var(--line); border-radius:8px; padding:9px; font:inherit; }
  textarea { min-height:120px; resize:vertical; }
  .row { display:flex; gap:8px; margin-top:8px; }
  button { padding:8px 14px; border:0; border-radius:8px; background:var(--accent);
           color:#0a0e1a; font-weight:600; cursor:pointer; }
  button.ghost { background:transparent; color:var(--accent); border:1px solid var(--line); font-weight:500; }
  ul.terms { list-style:none; padding:0; margin:12px 0 0; display:flex; flex-wrap:wrap; gap:8px; }
  ul.terms li { display:inline-flex; align-items:center; gap:8px; background:#0c0f1c;
          border:1px solid var(--line); border-radius:999px; padding:5px 6px 5px 12px; font-size:13px; }
  ul.terms li button { background:transparent; color:var(--muted); border:0; padding:0 4px;
          font-size:15px; cursor:pointer; line-height:1; }
  .status { margin-top:8px; color:var(--muted); font-size:13px; min-height:18px; }
  .desc { margin-top:10px; padding:10px; background:#0c0f1c; border:1px solid var(--line);
          border-radius:8px; font-size:13px; color:var(--muted); white-space:pre-wrap; }
</style>
</head>
<body>
<header>
  <h1>Account settings</h1>
  <div class="sp"></div>
  <a href="/app">← Editor</a>
  <a href="/auth/logout" id="logout">Log out</a>
</header>
<main>
  <section class="panel" id="dict">
    <h2>Personal dictionary</h2>
    <p class="hint">Words the engine should never flag or change — names, jargon,
       intentional spellings. Applied to every edit you make.</p>
    <div class="row">
      <input id="term" type="text" placeholder="e.g. Kubernetes" maxlength="80">
      <button id="add">Add</button>
    </div>
    <div class="status" id="dstatus"></div>
    <ul class="terms" id="terms"></ul>
  </section>

  <section class="panel" id="voice">
    <h2>Voice profile</h2>
    <p class="hint">Paste a few paragraphs you wrote. The engine matches this
       style so edits and drafts sound like you.</p>
    <textarea id="samples" placeholder="A few sentences in your own writing…"></textarea>
    <div class="row">
      <button id="save">Save</button>
      <button id="clear" class="ghost">Clear</button>
    </div>
    <div class="status" id="vstatus"></div>
    <div class="desc" id="desc" hidden></div>
  </section>
</main>
<script>
const $ = (id) => document.getElementById(id);

async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || ('HTTP ' + res.status));
  return data;
}

// --- dictionary ---
function renderTerms(terms) {
  $('terms').innerHTML = terms.map(t =>
    `<li>${escapeHtml(t)}<button data-term="${escapeHtml(t)}" title="Remove">×</button></li>`).join('');
  document.querySelectorAll('#terms button').forEach(b =>
    b.addEventListener('click', () => removeTerm(b.dataset.term)));
}
function escapeHtml(s){ return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
async function loadTerms() { try { renderTerms((await api('GET','/account/dictionary')).terms); } catch(e){ $('dstatus').textContent = e.message; } }
async function addTerm() {
  const term = $('term').value.trim();
  if (!term) return;
  try { renderTerms((await api('POST','/account/dictionary',{term})).terms); $('term').value=''; $('dstatus').textContent=''; }
  catch(e){ $('dstatus').textContent = e.message; }
}
async function removeTerm(term) {
  try { renderTerms((await api('DELETE','/account/dictionary',{term})).terms); }
  catch(e){ $('dstatus').textContent = e.message; }
}

// --- voice ---
function renderVoice(voice) {
  if (voice && voice.samples) {
    $('samples').value = voice.samples;
    $('desc').hidden = false;
    $('desc').textContent = 'Measured style: ' + (voice.descriptor || '(none)');
  } else {
    $('desc').hidden = true;
  }
}
async function loadVoice() { try { renderVoice((await api('GET','/account/voice')).voice); } catch(e){ $('vstatus').textContent = e.message; } }
async function saveVoice() {
  const samples = $('samples').value.trim();
  if (!samples) { $('vstatus').textContent = 'Paste a writing sample first.'; return; }
  try { renderVoice((await api('PUT','/account/voice',{samples})).voice); $('vstatus').textContent = 'Saved ✓'; }
  catch(e){ $('vstatus').textContent = e.message; }
}
async function clearVoice() {
  try { await api('DELETE','/account/voice'); $('samples').value=''; renderVoice(null); $('vstatus').textContent = 'Cleared.'; }
  catch(e){ $('vstatus').textContent = e.message; }
}

$('add').addEventListener('click', addTerm);
$('term').addEventListener('keydown', (e) => { if (e.key === 'Enter') addTerm(); });
$('save').addEventListener('click', saveVoice);
$('clear').addEventListener('click', clearVoice);
loadTerms();
loadVoice();
</script>
</body>
</html>
"""
