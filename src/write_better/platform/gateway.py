"""The versioned platform API gateway (#1 of the hard rules: one backend hub).

A WSGI app exposing ``/v1`` endpoints. Every surface (web, extension, add-ins,
CLI, SDKs) is a thin client of this gateway; none re-implement engine logic. The
gateway authenticates the caller (API key), enforces plan caps server-side, calls
the untouched engine, records usage for metering + analytics, and returns the
result plus live quota.

Endpoints (v1):
  GET  /v1            -> service + version + endpoint map
  GET  /v1/account    -> { email, plan }                         [auth]
  GET  /v1/usage      -> current-period quota + usage summary    [auth]
  POST /v1/improve    -> run the engine, metered + capped        [auth]
"""

from __future__ import annotations

import json
import os
import time
from collections import Counter
from urllib.parse import parse_qs

from ..citation import cite_batch, default_http
from ..context import normalize as normalize_context
from ..engine import Request, improve as engine_improve
from ..prompt import fold_sources
from ..voice import build_profile as build_voice_profile, render_voice_profile
from .. import localize
from .. import plans
from . import goals as goals_mod
from . import weekly
from ..modes import resolve_services
from ..prompt import VALID_FORMATS
from ..realtime import check_text, style_fingerprint

# Long-form context budget (chars). Over budget -> explicit warning, never a silent
# truncation. Our models carry 1M-token windows, so this is generous.
CONTEXT_BUDGET_CHARS = 200_000
from ..templating import (
    MissingFields, get_template, list_templates, load_templates, validate_and_render,
)
from . import accounts, analytics, metering, scans, teams

MAX_VARIANTS = 5
from .openapi import DOCS_PAGE, spec as openapi_spec
from .store import Store
from .vendors import VendorUnavailable, vendor_from_env

API_VERSION = "v1"
_CORS = ("Access-Control-Allow-Origin", "*")


def _html(start_response, status: str, html: str):
    body = html.encode("utf-8")
    start_response(status, [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        _CORS,
    ])
    return [body]


def _json(start_response, status: str, payload: dict, extra=()):
    body = json.dumps(payload).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        _CORS,
        *extra,
    ])
    return [body]


def _bearer(environ) -> str | None:
    auth = environ.get("HTTP_AUTHORIZATION", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):].strip()
    return environ.get("HTTP_X_API_KEY") or None


def _pos_int(value):
    """A positive int, or None for missing/blank/invalid (strict_limit caps)."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n > 0 else None


def _read_json(environ) -> tuple[dict | None, str | None]:
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
    if not isinstance(data, dict):
        return None, "JSON body must be an object"
    return data, None


def make_gateway(store: Store, engine=engine_improve, vendor="env",
                 citation_http=default_http, mailer=None, base_url=""):
    """Build the gateway WSGI app over ``store``.

    ``engine``, ``vendor`` (plagiarism/AI scan provider), ``citation_http``
    (HTTP fetch for citation resolvers), and ``mailer`` (weekly-email transport)
    are injectable for tests; ``vendor="env"`` resolves it from
    ``ORIGINALITY_API_KEY`` (None if unset).
    """
    if mailer is None:
        from .mailer import ConsoleMailer
        mailer = ConsoleMailer()
    if vendor == "env":
        vendor = vendor_from_env()

    def app(environ, start_response):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/").rstrip("/") or "/"

        if method == "OPTIONS":
            start_response("204 No Content", [
                _CORS,
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key"),
                ("Content-Length", "0"),
            ])
            return [b""]

        # Public: version/info
        if path in ("/v1", "/") and method == "GET":
            return _json(start_response, "200 OK", {
                "service": "help-me-write-better",
                "api_version": API_VERSION,
                "auth": "Bearer <api-key> or X-API-Key header",
                "endpoints": {
                    "GET /v1/account": "your account + plan",
                    "GET /v1/usage": "current-period quota + usage",
                    "GET /v1/analytics": "writing analytics + weekly insights",
                    "GET /v1/history": "recent requests (metadata only)",
                    "GET|PUT /v1/preferences": "synced user preferences",
                    "GET|POST /v1/documents": "list / create saved documents",
                    "GET|PATCH|DELETE /v1/documents/{id}": "fetch / rename / delete a document",
                    "GET|POST /v1/documents/{id}/versions": "list / add a version",
                    "POST /v1/documents/{id}/versions/{vid}/restore": "restore a past version",
                    "GET|POST|DELETE /v1/snippets": "manage text snippets (client-side expansion)",
                    "GET|PUT /v1/goals": "writing goals + progress trend",
                    "POST /v1/improve": "run the engine (metered, capped)",
                    "POST /v1/check": "real-time inline check (local, uncapped)",
                    "POST /v1/fingerprint": "prose style fingerprint (local, uncapped)",
                    "POST /v1/scan": "plagiarism / AI-detection scan (external, metered)",
                    "GET /v1/scans/{id}": "fetch a scan result",
                    "POST /v1/cite": "generate/format citations (DOI/ISBN/URL/free-text)",
                    "GET /v1/citations": "your saved bibliography",
                    "GET /v1/templates": "template library (drives dynamic forms)",
                    "GET /v1/openapi.json": "the OpenAPI 3.1 contract",
                    "GET /v1/docs": "human-readable API docs",
                },
            })

        # Public: machine-readable spec + docs viewer.
        if path == "/v1/openapi.json" and method == "GET":
            return _json(start_response, "200 OK", openapi_spec())
        if path == "/v1/docs" and method == "GET":
            return _html(start_response, "200 OK", DOCS_PAGE)

        # Public: weekly-email cron (shared secret) + one-click unsubscribe (signed
        # token). No login — the unsubscribe link is clicked from an email.
        if path == "/v1/cron/weekly-email" and method in ("GET", "POST"):
            return _cron_weekly_email(store, mailer, base_url, environ, start_response)
        if path == "/v1/unsubscribe" and method == "GET":
            return _unsubscribe(store, environ, start_response)

        # Everything else requires authentication.
        user = accounts.authenticate_key(store, _bearer(environ))
        if user is None:
            return _json(start_response, "401 Unauthorized",
                         {"error": "missing or invalid API key", "code": "unauthorized"})

        parts = [p for p in path.split("/") if p]  # e.g. ['v1','documents','5','versions']
        rest = parts[1:]

        if rest == ["account"] and method == "GET":
            return _json(start_response, "200 OK",
                         {"email": user["email"], "plan": user["plan"]})

        if rest == ["usage"] and method == "GET":
            return _json(start_response, "200 OK", {
                "quota": metering.quota(store, user),
                "summary": store.usage_since(user["id"], metering.period_start()),
            })

        if rest == ["history"] and method == "GET":
            return _json(start_response, "200 OK",
                         {"history": store.history(user["id"])})

        if rest == ["preferences"]:
            return _preferences(store, user, method, environ, start_response)

        if rest == ["snippets"]:
            return _snippets(store, user, method, environ, start_response)

        if rest == ["goals"]:
            return _goals(store, user, method, environ, start_response)

        if rest == ["dictionary"]:
            return _dictionary(store, user, method, environ, start_response)

        if rest == ["voice"]:
            return _voice(store, user, method, environ, start_response)

        if rest and rest[0] == "documents":
            return _documents(store, user, rest, method, environ, start_response)

        if rest == ["improve"] and method == "POST":
            return _improve(store, engine, user, environ, start_response)

        if rest == ["check"] and method == "POST":
            return _check(store, user, environ, start_response)

        if rest == ["fingerprint"] and method == "POST":
            return _fingerprint(store, user, environ, start_response)

        if rest == ["scan"] and method == "POST":
            return _scan(store, vendor, user, environ, start_response)

        if rest[:1] == ["scans"] and len(rest) == 2 and method == "GET":
            result = scans.get(store, user, rest[1])
            if result is None:
                return _json(start_response, "404 Not Found", {"error": "no such scan"})
            return _json(start_response, "200 OK", result)

        if rest == ["templates"] and method == "GET":
            qs = parse_qs(environ.get("QUERY_STRING", ""))
            category = (qs.get("category") or [None])[0]
            return _json(start_response, "200 OK", {"templates": list_templates(category)})

        if rest == ["cite"] and method == "POST":
            return _cite(store, citation_http, user, environ, start_response)

        if rest == ["citations"] and method == "GET":
            return _json(start_response, "200 OK",
                         {"citations": store.list_citations(user["id"])})

        if rest == ["analytics"] and method == "GET":
            qs = parse_qs(environ.get("QUERY_STRING", ""))
            try:
                days = max(1, min(int((qs.get("window") or ["7"])[0]), 90))
            except ValueError:
                days = 7
            since = int(time.time()) - days * 86400
            return _json(start_response, "200 OK", {
                "window_days": days,
                "summary": analytics.summarize(store, user["id"], since),
                "insights": analytics.weekly_insights(store, user["id"]),
            })

        if rest and rest[0] == "team":
            return _team(store, user, rest, method, environ, start_response)

        return _json(start_response, "404 Not Found", {"error": "no such endpoint"})

    return app


def _team(store, user, rest, method, environ, start_response):
    uid = user["id"]

    if rest == ["team"]:
        if method == "GET":
            org = store.get_org_for_user(uid)
            if not org:
                return _json(start_response, "200 OK", {"org": None})
            return _json(start_response, "200 OK", {"org": _org_view(store, org, uid)})
        if method == "POST":
            if store.get_org_for_user(uid):
                return _json(start_response, "400 Bad Request",
                             {"error": "you already belong to a team"})
            data, err = _read_json(environ)
            if err:
                return _json(start_response, "400 Bad Request", {"error": err})
            name = (data.get("name") or "").strip()
            if not name:
                return _json(start_response, "400 Bad Request", {"error": "'name' is required"})
            org = teams.create_org(store, name, user, plan=user.get("plan", "business"))
            return _json(start_response, "201 Created", {"org": _org_view(store, org, uid)})
        return _json(start_response, "405 Method Not Allowed", {"error": "use GET or POST"})

    org = store.get_org_for_user(uid)
    if not org:
        return _json(start_response, "404 Not Found", {"error": "you are not in a team"})
    org_id = org["id"]

    try:
        if rest == ["team", "style-guide"]:
            if method == "GET":
                return _json(start_response, "200 OK",
                             {"style_guide": teams.get_style_guide(store, org_id)})
            if method in ("PUT", "POST"):
                data, err = _read_json(environ)
                if err:
                    return _json(start_response, "400 Bad Request", {"error": err})
                guide = teams.set_style_guide(store, org_id, uid, data)
                return _json(start_response, "200 OK", {"style_guide": guide})

        if rest == ["team", "members"]:
            if method == "GET":
                return _json(start_response, "200 OK",
                             {"members": store.list_org_members(org_id)})
            if method == "POST":
                data, err = _read_json(environ)
                if err:
                    return _json(start_response, "400 Bad Request", {"error": err})
                target = store.get_user_by_email((data.get("email") or "").strip())
                if not target:
                    return _json(start_response, "404 Not Found",
                                 {"error": "no user with that email"})
                member = teams.add_member(store, org_id, uid, target,
                                          role=data.get("role", "member"))
                return _json(start_response, "201 Created", {"member": member})

        if rest[:2] == ["team", "members"] and len(rest) == 3 and method == "DELETE":
            teams.remove_member(store, org_id, uid, int(rest[2]))
            return _json(start_response, "200 OK", {"removed": True})

        if rest == ["team", "analytics"] and method == "GET":
            teams.require_admin(store, org_id, uid)
            since = int(time.time()) - 30 * 86400
            return _json(start_response, "200 OK",
                         {"rollup": analytics.rollup(store, store.org_member_ids(org_id), since)})

    except teams.PermissionError_ as exc:
        return _json(start_response, "403 Forbidden", {"error": str(exc)})
    except teams.SeatLimitError as exc:
        return _json(start_response, "402 Payment Required",
                     {"error": str(exc), "code": "seat_limit"})
    except ValueError as exc:
        return _json(start_response, "400 Bad Request", {"error": str(exc)})

    return _json(start_response, "404 Not Found", {"error": "no such endpoint"})


def _org_view(store, org, user_id):
    member = store.get_org_member(org["id"], user_id)
    return {
        "id": org["id"], "name": org["name"], "plan": org["plan"],
        "seats": org["seats"], "seats_used": store.count_org_members(org["id"]),
        "role": member["role"] if member else None,
        "members": store.list_org_members(org["id"]),
    }


def _cite(store, http, user, environ, start_response):
    """Citation generator/formatter (Feature 3). Free; no external key needed."""
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    opts = data.get("cite") if isinstance(data.get("cite"), dict) else data
    inputs = opts.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        return _json(start_response, "400 Bad Request",
                     {"error": "'cite.inputs' (non-empty array) is required"})
    style = opts.get("style", "apa")
    output = opts.get("output") or ["bibliography", "in_text"]
    result = cite_batch(inputs, style, http, output=tuple(output))

    if opts.get("save"):
        doc_id = opts.get("doc_id")
        for item in result["items"]:
            store.insert_citation(user["id"], item["csl_json"], result["style"], doc_id)

    store.insert_usage(user["id"], "citation_generated", "none", premium=False,
                       input_tokens=0, output_tokens=0,
                       issue_types={it["resolver"]: 1 for it in result["items"]})
    # Adoption breakdown by citation style.
    store.insert_usage(user["id"], "cite_style", "none", premium=False,
                       input_tokens=0, output_tokens=0,
                       issue_types={result["style"]: 1})
    return _json(start_response, "200 OK", result)


def _scan(store, vendor, user, environ, start_response):
    """Plagiarism / AI-detection scan (Features 1 & 2). External + metered."""
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return _json(start_response, "400 Bad Request", {"error": "'text' is required"})
    opts = data.get("check") if isinstance(data.get("check"), dict) else {}
    modes = opts.get("modes") or data.get("modes") or ["plagiarism"]
    try:
        min_match = float(opts.get("min_match_pct", data.get("min_match_pct", 1.0)))
    except (TypeError, ValueError):
        min_match = 1.0

    try:
        result = scans.submit(store, user, text, modes, vendor,
                              min_match_pct=min_match,
                              period_start=metering.period_start())
    except scans.ScanCapError as exc:
        return _json(start_response, "402 Payment Required", {
            "error": (f"scan credit cap reached "
                      f"({exc.quota['scan_credits_used']}/{exc.quota['scan_cap']} this period)"),
            "code": "scan_cap_reached", "quota": exc.quota})
    except VendorUnavailable as exc:
        return _json(start_response, "503 Service Unavailable", {
            "error": str(exc), "code": "feature_unavailable",
            "retry_after": exc.retry_after}, extra=[("Retry-After", str(exc.retry_after))])

    # Analytics event (feature adoption); the scan itself is metered via credits.
    store.insert_usage(user["id"], "scan_completed", "vendor", premium=False,
                       input_tokens=0, output_tokens=0, words=analytics.word_count(text),
                       issue_types={k: 1 for k in result if k in ("plagiarism", "ai_detection")})
    return _json(start_response, "200 OK", result)


def _check(store, user, environ, start_response):
    """Real-time inline check — local rules, uncapped (no premium generation)."""
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    text = data.get("text")
    if not isinstance(text, str):
        return _json(start_response, "400 Bad Request", {"error": "'text' (string) is required"})
    previous = data.get("previous")
    # A team member's check enforces the org style guide (banned/preferred terms).
    org = store.get_org_for_user(user["id"])
    banned, preferred = ([], {})
    if org:
        banned, preferred = teams.banned_and_preferred(teams.get_style_guide(store, org["id"]))
    suggestions = check_text(text, previous if isinstance(previous, str) else None,
                             banned_terms=banned, preferred_terms=preferred)
    issue_types = Counter(s.type for s in suggestions)

    # Meter every call (hard rule #3) — local checks are uncapped, ~0 cost.
    store.insert_usage(user["id"], "realtime-check", "local", premium=False,
                       input_tokens=0, output_tokens=0,
                       words=analytics.word_count(text),
                       suggestions=len(suggestions), issue_types=dict(issue_types))

    return _json(start_response, "200 OK", {
        "suggestions": [s.to_dict() for s in suggestions],
        "count": len(suggestions),
    })


def _preferences(store, user, method, environ, start_response):
    if method == "GET":
        return _json(start_response, "200 OK",
                     {"preferences": store.get_preferences(user["id"])})
    if method in ("PUT", "POST"):
        data, err = _read_json(environ)
        if err:
            return _json(start_response, "400 Bad Request", {"error": err})
        return _json(start_response, "200 OK",
                     {"preferences": store.set_preferences(user["id"], data)})
    return _json(start_response, "405 Method Not Allowed", {"error": "use GET or PUT"})


def _valid_trigger(trigger: str):
    if not trigger:
        return False, "'trigger' is required"
    if len(trigger) > 32:
        return False, "trigger must be 32 characters or fewer"
    if any(c.isspace() for c in trigger):
        return False, "trigger must not contain whitespace"
    return True, ""


def _snippets(store, user, method, environ, start_response):
    """Per-user text snippets. Expansion is client-side; the engine never sees these."""
    uid = user["id"]
    if method == "GET":
        return _json(start_response, "200 OK", {"snippets": store.list_snippets(uid)})
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    trigger = (data.get("trigger") or "").strip()
    if method == "POST":
        ok, msg = _valid_trigger(trigger)
        if not ok:
            return _json(start_response, "400 Bad Request", {"error": msg})
        body = data.get("body")
        if not isinstance(body, str) or not body:
            return _json(start_response, "400 Bad Request", {"error": "'body' is required"})
        snip = store.upsert_snippet(uid, trigger, body)
        return _json(start_response, "201 Created",
                     {"snippet": snip, "snippets": store.list_snippets(uid)})
    if method == "DELETE":
        if not store.remove_snippet(uid, trigger):
            return _json(start_response, "404 Not Found",
                         {"error": f"no snippet {trigger!r}"})
        return _json(start_response, "200 OK", {"snippets": store.list_snippets(uid)})
    return _json(start_response, "405 Method Not Allowed",
                 {"error": "use GET, POST, or DELETE"})


def _goals(store, user, method, environ, start_response):
    """Personal writing goals + progress trend (progress framing only, no streaks)."""
    uid = user["id"]
    prefs = store.get_preferences(uid)
    if method == "GET":
        selected = goals_mod.normalize(prefs.get("goals"))
        return _json(start_response, "200 OK", {
            "goals": selected,
            "categories": list(goals_mod.GOAL_CATEGORIES),
            "trend": goals_mod.trend(store, uid, selected)})
    if method in ("PUT", "POST"):
        data, err = _read_json(environ)
        if err:
            return _json(start_response, "400 Bad Request", {"error": err})
        selected = goals_mod.normalize(data.get("goals"))
        prefs["goals"] = selected
        store.set_preferences(uid, prefs)
        store.insert_usage(uid, "goal_set", "none", premium=False,
                           input_tokens=0, output_tokens=0,
                           issue_types={g: 1 for g in selected})
        return _json(start_response, "200 OK",
                     {"goals": selected, "trend": goals_mod.trend(store, uid, selected)})
    return _json(start_response, "405 Method Not Allowed", {"error": "use GET or PUT"})


def _cron_weekly_email(store, mailer, base_url, environ, start_response):
    """Send the weekly recap to opted-in users. Guarded by a shared secret; only
    composes for explicit opt-ins (unsubscribed users are never built)."""
    secret = os.environ.get("WB_CRON_SECRET")
    given = (parse_qs(environ.get("QUERY_STRING", "")).get("secret") or [None])[0]
    given = given or environ.get("HTTP_X_CRON_SECRET")
    if not secret or given != secret:
        return _json(start_response, "403 Forbidden",
                     {"error": "missing or invalid cron secret"})
    sent = 0
    for u in store.weekly_email_recipients():
        insights = analytics.weekly_insights(store, u["id"])
        mailer.send(weekly.compose(u, insights, base_url))
        store.insert_usage(u["id"], "weekly_email_sent", "none", premium=False,
                           input_tokens=0, output_tokens=0)
        sent += 1
    return _json(start_response, "200 OK", {"sent": sent})


def _unsubscribe(store, environ, start_response):
    qs = parse_qs(environ.get("QUERY_STRING", ""))
    uid = (qs.get("u") or [None])[0]
    token = (qs.get("token") or [None])[0]
    if not weekly.verify_unsubscribe(uid, token):
        return _json(start_response, "400 Bad Request",
                     {"error": "invalid or expired unsubscribe link"})
    prefs = store.get_preferences(int(uid))
    prefs["weekly_email"] = False
    store.set_preferences(int(uid), prefs)
    return _html(start_response, "200 OK",
                 "<!doctype html><meta charset=utf-8><p>You're unsubscribed from the "
                 "weekly writing recap. You can re-enable it anytime in settings.</p>")


def _dictionary(store, user, method, environ, start_response):
    """Personal dictionary CRUD. These terms are injected into every improve call
    as PROTECTED TERMS the engine must never flag or change."""
    uid = user["id"]
    if method == "GET":
        return _json(start_response, "200 OK", {"terms": store.list_dictionary(uid)})

    if method in ("POST", "DELETE"):
        data, err = _read_json(environ)
        if err:
            return _json(start_response, "400 Bad Request", {"error": err})
        term = (data.get("term") or "").strip()
        if not term:
            return _json(start_response, "400 Bad Request", {"error": "'term' is required"})
        if method == "POST":
            store.add_dictionary_term(uid, term)
            return _json(start_response, "201 Created", {"terms": store.list_dictionary(uid)})
        # DELETE
        removed = store.remove_dictionary_term(uid, term)
        if not removed:
            return _json(start_response, "404 Not Found", {"error": f"term {term!r} not in dictionary"})
        return _json(start_response, "200 OK", {"terms": store.list_dictionary(uid)})

    return _json(start_response, "405 Method Not Allowed",
                 {"error": "use GET, POST, or DELETE"})


def _voice(store, user, method, environ, start_response):
    """Personal voice profile CRUD. The stored samples are turned into a VOICE
    PROFILE and injected into every improve call so output sounds like the user."""
    uid = user["id"]
    if method == "GET":
        vp = store.get_voice_profile(uid)
        return _json(start_response, "200 OK",
                     {"voice": build_voice_profile(vp["samples"]) if vp else None})

    if method in ("PUT", "POST"):
        data, err = _read_json(environ)
        if err:
            return _json(start_response, "400 Bad Request", {"error": err})
        samples = (data.get("samples") or "").strip()
        if not samples:
            return _json(start_response, "400 Bad Request",
                         {"error": "'samples' is required (paste a few paragraphs you wrote)"})
        store.set_voice_profile(uid, samples)
        return _json(start_response, "201 Created", {"voice": build_voice_profile(samples)})

    if method == "DELETE":
        store.clear_voice_profile(uid)
        return _json(start_response, "200 OK", {"voice": None})

    return _json(start_response, "405 Method Not Allowed",
                 {"error": "use GET, PUT, or DELETE"})


def _documents(store, user, rest, method, environ, start_response):
    uid = user["id"]

    # /v1/documents  -> list / create
    if rest == ["documents"]:
        if method == "GET":
            return _json(start_response, "200 OK", {"documents": store.list_documents(uid)})
        if method == "POST":
            data, err = _read_json(environ)
            if err:
                return _json(start_response, "400 Bad Request", {"error": err})
            content = data.get("content")
            if not isinstance(content, str):
                return _json(start_response, "400 Bad Request",
                             {"error": "'content' (string) is required to save a document"})
            doc = store.create_document(uid, data.get("title") or "Untitled", content)
            return _json(start_response, "201 Created", {"document": doc})
        return _json(start_response, "405 Method Not Allowed", {"error": "use GET or POST"})

    # everything below needs a numeric document id
    try:
        doc_id = int(rest[1])
    except (IndexError, ValueError):
        return _json(start_response, "404 Not Found", {"error": "invalid document id"})

    # /v1/documents/{id}/versions -> list / add
    if rest[2:] == ["versions"]:
        if method == "GET":
            versions = store.list_document_versions(uid, doc_id)
            if versions is None:
                return _json(start_response, "404 Not Found", {"error": "no such document"})
            return _json(start_response, "200 OK", {"versions": versions})
        if method == "POST":
            data, err = _read_json(environ)
            if err:
                return _json(start_response, "400 Bad Request", {"error": err})
            content = data.get("content")
            if not isinstance(content, str):
                return _json(start_response, "400 Bad Request",
                             {"error": "'content' (string) is required"})
            doc = store.add_document_version(uid, doc_id, content)
            if doc is None:
                return _json(start_response, "404 Not Found", {"error": "no such document"})
            store.prune_document_versions(doc_id, plans.version_cap(user.get("plan")))
            return _json(start_response, "201 Created", {"document": doc})
        return _json(start_response, "405 Method Not Allowed", {"error": "use GET or POST"})

    # /v1/documents/{id}/versions/{vid}/restore -> make a past version current
    if len(rest) == 5 and rest[2] == "versions" and rest[4] == "restore":
        if method != "POST":
            return _json(start_response, "405 Method Not Allowed", {"error": "use POST"})
        try:
            version_id = int(rest[3])
        except ValueError:
            return _json(start_response, "404 Not Found", {"error": "invalid version id"})
        doc = store.restore_document_version(uid, doc_id, version_id)
        if doc is None:
            return _json(start_response, "404 Not Found",
                         {"error": "no such document or version"})
        store.prune_document_versions(doc_id, plans.version_cap(user.get("plan")))
        return _json(start_response, "201 Created", {"document": doc})

    # /v1/documents/{id} -> get / rename / delete
    if rest[2:] == []:
        if method == "GET":
            doc = store.get_document(uid, doc_id)
            if doc is None:
                return _json(start_response, "404 Not Found", {"error": "no such document"})
            return _json(start_response, "200 OK", {"document": doc})
        if method in ("PATCH", "POST"):
            data, err = _read_json(environ)
            if err:
                return _json(start_response, "400 Bad Request", {"error": err})
            doc = store.rename_document(uid, doc_id, data.get("title") or "Untitled")
            if doc is None:
                return _json(start_response, "404 Not Found", {"error": "no such document"})
            return _json(start_response, "200 OK", {"document": doc})
        if method == "DELETE":
            ok = store.delete_document(uid, doc_id)
            status = "200 OK" if ok else "404 Not Found"
            return _json(start_response, status, {"deleted": ok})

    return _json(start_response, "404 Not Found", {"error": "no such endpoint"})


def _improve(store, engine, user, environ, start_response):
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})

    # Template path (Features 4 & 5): render a versioned prompt config into `text`.
    n_variants = 1
    if data.get("template"):
        tpl = get_template(data["template"])
        if not tpl:
            return _json(start_response, "422 Unprocessable Entity", {
                "error": f"unknown template {data['template']!r}", "code": "unknown_template",
                "templates": list(load_templates().keys())})
        try:
            rendered = validate_and_render(tpl, data.get("template_fields") or {})
        except MissingFields as exc:
            return _json(start_response, "422 Unprocessable Entity", {
                "error": str(exc), "code": "missing_fields", "missing": exc.missing,
                "fields": list(tpl.fields)})
        data = {**data, "text": rendered,
                "services": data.get("services") or tpl.defaults.get("service", "write"),
                "format": data.get("format") or tpl.defaults.get("format", "markdown")}
        n_variants = max(1, min(int(data.get("variants") or tpl.variants or 1), MAX_VARIANTS))

    # `merge` accepts a `texts` array; fold it into one delimited TEXT.
    texts = data.get("texts")
    if isinstance(texts, list) and any(str(t).strip() for t in texts):
        text = fold_sources(texts)
    else:
        text = (data.get("text") or "").strip()
    if not text:
        return _json(start_response, "400 Bad Request", {"error": "'text' is required"})

    output_format = data.get("format", "markdown")
    if output_format not in VALID_FORMATS:
        return _json(start_response, "400 Bad Request",
                     {"error": f"unknown format {output_format!r}",
                      "formats": list(VALID_FORMATS)})

    try:
        modes = resolve_services(data.get("services") or "clarify")
    except ValueError as exc:
        return _json(start_response, "400 Bad Request", {"error": str(exc)})

    # `localize-tone` requires a supported `culture`; unknown -> 422 with the list.
    free_form = data.get("request")
    if any(m.name == "localize-tone" for m in modes):
        culture = data.get("culture")
        if not localize.is_supported(culture):
            return _json(start_response, "422 Unprocessable Entity",
                         {"error": f"unknown culture {culture!r}",
                          "code": "unknown_culture", "supported": localize.ids()})
        free_form = localize.augment(free_form, culture)

    # Enforce the plan cap BEFORE spending on the engine. For variants, clamp to
    # what the plan allows (premium services consume one generation each).
    allowed, q = metering.check_allowed(store, user, modes)
    if not allowed:
        return _json(start_response, "402 Payment Required", {
            "error": (f"plan '{q['plan']}' premium-generation cap reached "
                      f"({q['premium_used']}/{q['premium_cap']} this period)"),
            "code": "cap_reached",
            "quota": q,
        })
    if metering.consumes_premium(modes) and n_variants > 1:
        n_variants = max(1, min(n_variants, q["premium_remaining"]))

    # Inject the team style guide (if any) so every member's writing conforms.
    org = store.get_org_for_user(user["id"])
    style_guide = teams.render_style_guide(teams.get_style_guide(store, org["id"])) if org else None

    # Inject the user's personal voice profile ("sounds like me"), if they've set one.
    vp = store.get_voice_profile(user["id"])
    voice_profile = render_voice_profile(vp["samples"]) if vp else None

    # Long-form context: typed {text, role} (or a plain string). The engine
    # front-trims over-budget context and reports it via context_truncated.
    warnings = []
    context_text, context_role = normalize_context(data.get("context"))

    req = Request(
        text=text,
        services=[m.name for m in modes],
        output_format=output_format,
        show_changes=bool(data.get("show_changes", False)),
        audience=data.get("audience"),
        tone=data.get("tone"),
        length=data.get("length"),
        reading_level=data.get("reading_level"),
        language=data.get("language"),
        free_form=free_form,
        model=data.get("model"),
        effort=data.get("effort", "high"),
        style_guide=style_guide or None,
        context=context_text or None,
        context_role=context_role,
        protected_terms=store.list_dictionary(user["id"]),
        voice_profile=voice_profile,
        max_chars=_pos_int(data.get("max_chars")),
        max_words=_pos_int(data.get("max_words")),
    )

    outputs, last = [], None
    in_tokens = out_tokens = 0
    for _ in range(n_variants):
        try:
            last = engine(req)
        except Exception as exc:  # surface engine/SDK errors cleanly
            return _json(start_response, "502 Bad Gateway",
                         {"error": f"generation failed: {exc}"})
        outputs.append(last.text)
        in_tokens += last.input_tokens
        out_tokens += last.output_tokens
        # Meter each generation (feeds billing + analytics).
        metering.record(store, user, last.services, last.model,
                        last.input_tokens, last.output_tokens,
                        words=analytics.word_count(text))

    body = {
        "text": outputs[0],
        "model": last.model,
        "services": [m.name for m in last.services],
        "usage": {"input_tokens": in_tokens, "output_tokens": out_tokens},
        "quota": metering.quota(store, user),
        "length": {"chars": last.char_count, "words": last.word_count},
        "limit_met": last.limit_met,
    }
    if last.context_truncated:
        body["context_truncated"] = last.context_truncated
    if data.get("template"):
        body["template"] = data["template"]
        body["variants"] = outputs
        # Analytics event: which template was used.
        store.insert_usage(user["id"], "template_used", "none", premium=False,
                           input_tokens=0, output_tokens=0,
                           issue_types={data["template"]: 1})
    # Feature-adoption events for the depth services.
    mode_names = {m.name for m in modes}
    if "merge" in mode_names:
        store.insert_usage(user["id"], "merge_run", "none", premium=False,
                           input_tokens=0, output_tokens=0)
    if "argument-check" in mode_names:
        store.insert_usage(user["id"], "argument_check_run", "none", premium=False,
                           input_tokens=0, output_tokens=0)
    if warnings:
        body["warnings"] = warnings
    return _json(start_response, "200 OK", body)


def _fingerprint(store, user, environ, start_response):
    """Style fingerprint (Feature 5) — local prose metrics, uncapped + free."""
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})
    text = data.get("text")
    if not isinstance(text, str) or not text.strip():
        return _json(start_response, "400 Bad Request", {"error": "'text' is required"})
    fp = style_fingerprint(text)
    store.insert_usage(user["id"], "style-fingerprint", "local", premium=False,
                       input_tokens=0, output_tokens=0, words=fp["words"])
    return _json(start_response, "200 OK", {"fingerprint": fp})


# Lazily-built default app for deployment (uses WB_DB_PATH; real engine).
_default_app = None


def app(environ, start_response):  # pragma: no cover - thin deploy shim
    global _default_app
    if _default_app is None:
        _default_app = make_gateway(Store(os.environ.get("WB_DB_PATH", "wb.db")))
    return _default_app(environ, start_response)
