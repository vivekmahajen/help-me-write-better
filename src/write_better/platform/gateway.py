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

from ..engine import Request, improve as engine_improve
from ..modes import resolve_services
from ..prompt import VALID_FORMATS
from . import accounts, metering
from .store import Store

API_VERSION = "v1"
_CORS = ("Access-Control-Allow-Origin", "*")


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


def make_gateway(store: Store, engine=engine_improve):
    """Build the gateway WSGI app over ``store``. ``engine`` is injectable for tests."""

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
                    "POST /v1/improve": "run the engine (metered, capped)",
                },
            })

        # Everything else requires authentication.
        user = accounts.authenticate_key(store, _bearer(environ))
        if user is None:
            return _json(start_response, "401 Unauthorized",
                         {"error": "missing or invalid API key", "code": "unauthorized"})

        if path == "/v1/account" and method == "GET":
            return _json(start_response, "200 OK",
                         {"email": user["email"], "plan": user["plan"]})

        if path == "/v1/usage" and method == "GET":
            return _json(start_response, "200 OK", {
                "quota": metering.quota(store, user),
                "summary": store.usage_since(user["id"], metering.period_start()),
            })

        if path == "/v1/improve" and method == "POST":
            return _improve(store, engine, user, environ, start_response)

        return _json(start_response, "404 Not Found", {"error": "no such endpoint"})

    return app


def _improve(store, engine, user, environ, start_response):
    data, err = _read_json(environ)
    if err:
        return _json(start_response, "400 Bad Request", {"error": err})

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

    # Enforce the plan cap BEFORE spending on the engine.
    allowed, q = metering.check_allowed(store, user, modes)
    if not allowed:
        return _json(start_response, "402 Payment Required", {
            "error": (f"plan '{q['plan']}' premium-generation cap reached "
                      f"({q['premium_used']}/{q['premium_cap']} this period)"),
            "code": "cap_reached",
            "quota": q,
        })

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
        free_form=data.get("request"),
        model=data.get("model"),
        effort=data.get("effort", "high"),
    )

    try:
        result = engine(req)
    except Exception as exc:  # surface engine/SDK errors cleanly
        return _json(start_response, "502 Bad Gateway",
                     {"error": f"generation failed: {exc}"})

    # Meter the completed call (feeds billing + analytics).
    metering.record(store, user, result.services, result.model,
                    result.input_tokens, result.output_tokens)

    return _json(start_response, "200 OK", {
        "text": result.text,
        "model": result.model,
        "services": [m.name for m in result.services],
        "usage": {"input_tokens": result.input_tokens,
                  "output_tokens": result.output_tokens},
        "quota": metering.quota(store, user),
    })


# Lazily-built default app for deployment (uses WB_DB_PATH; real engine).
_default_app = None


def app(environ, start_response):  # pragma: no cover - thin deploy shim
    global _default_app
    if _default_app is None:
        _default_app = make_gateway(Store(os.environ.get("WB_DB_PATH", "wb.db")))
    return _default_app(environ, start_response)
