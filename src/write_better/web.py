"""A tiny stdlib WSGI app exposing the Write Better engine over HTTP.

Kept dependency-free (only the engine, which lazily imports the Anthropic SDK)
so it deploys cleanly on Vercel's Python runtime. Routing keys off the method
and, for browser GETs, a coarse path so it still works behind a catch-all
rewrite:

    GET  /      (Accept: text/html) -> marketing landing page
    GET  /app   (Accept: text/html) -> the demo editor (with ?service= preselect)
    GET  /      (anything else)     -> service info (services + request shape)
    POST        (any path)          -> run the engine, return the polished text
    OPTIONS                         -> CORS preflight

The JSON descriptor (``_info``) and ``POST`` behaviour are deliberately
unchanged — content negotiation only ever *adds* the HTML branches.
"""

from __future__ import annotations

import json
import os

from . import landing
from .demo import RateLimiter, run_demo
from .engine import Request, has_api_key, improve
from .modes import MODES, resolve_services
from .prompt import VALID_FORMATS
from .samples import SAMPLES
from .ui import PAGE

_CORS = ("Access-Control-Allow-Origin", "*")

# Per-IP cap for the public hero demo (POST /demo); over the cap it returns a
# clearly-labelled canned sample instead of a live call.
_DEMO_LIMITER = RateLimiter(limit=int(os.environ.get("WB_DEMO_LIMIT", "5")), window=3600.0)


def _client_ip(environ) -> str:
    fwd = environ.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return environ.get("REMOTE_ADDR", "unknown")


def _html(start_response, status: str, html: str):
    body = html.encode("utf-8")
    start_response(status, [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
        _CORS,
    ])
    return [body]


def _respond(start_response, status: str, payload: dict, extra_headers=()):
    body = json.dumps(payload).encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        _CORS,
        *extra_headers,
    ]
    start_response(status, headers)
    return [body]


def _info() -> dict:
    return {
        "service": "help-me-write-better",
        "description": "Improve and format text with Claude, preserving meaning and voice.",
        "request": {
            "method": "POST",
            "content_type": "application/json",
            "body": {
                "text": "<required> the text to improve",
                "services": "one or more of the services below (string or list); default: clarify",
                "format": "one of the formats below; default: markdown",
                "show_changes": "bool; include a summary of edits; default: false",
                "tone": "optional",
                "audience": "optional",
                "length": "optional",
                "reading_level": "optional",
                "language": "optional (for translate)",
                "request": "optional free-form instruction",
                "model": "optional model id override",
                "effort": "low | medium | high | max; default: high",
            },
        },
        "services": [m.name for m in MODES],
        "formats": list(VALID_FORMATS),
        "samples": SAMPLES,
    }


def app(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET").upper()

    if method == "OPTIONS":
        start_response("204 No Content", [
            _CORS,
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
            ("Access-Control-Allow-Headers", "Content-Type"),
            ("Content-Length", "0"),
        ])
        return [b""]

    if method == "GET":
        # Browsers (Accept: text/html) get a page; everyone else gets JSON.
        if "text/html" in environ.get("HTTP_ACCEPT", ""):
            # /app -> the demo editor; anything else -> the landing page,
            # rendered fresh so the FEATURES_LIVE honesty gate reflects config.
            route = (environ.get("PATH_INFO", "/") or "/").rstrip("/")
            page = PAGE if route.endswith("/app") else landing.render()
            return _html(start_response, "200 OK", page)
        return _respond(start_response, "200 OK", _info())

    if method != "POST":
        return _respond(start_response, "405 Method Not Allowed", {"error": "use GET or POST"})

    # --- POST: run the engine ---
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    raw = environ["wsgi.input"].read(length) if length > 0 else b""

    try:
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (ValueError, UnicodeDecodeError):
        return _respond(start_response, "400 Bad Request",
                        {"error": "request body must be valid JSON"})
    if not isinstance(data, dict):
        return _respond(start_response, "400 Bad Request",
                        {"error": "JSON body must be an object"})

    # The public hero demo: rate-limited, always 200, falls back to a labelled
    # sample. Kept off the main POST path so the engine API is unchanged.
    if (environ.get("PATH_INFO", "/") or "/").rstrip("/").endswith("/demo"):
        result = run_demo(data.get("text") or "", _client_ip(environ),
                          limiter=_DEMO_LIMITER, improve_fn=improve,
                          key_present=has_api_key())
        return _respond(start_response, "200 OK", result.payload())

    text = (data.get("text") or "").strip()
    if not text:
        return _respond(start_response, "400 Bad Request", {"error": "'text' is required"})

    output_format = data.get("format", "markdown")
    if output_format not in VALID_FORMATS:
        return _respond(start_response, "400 Bad Request",
                        {"error": f"unknown format {output_format!r}",
                         "formats": list(VALID_FORMATS)})

    try:
        services = resolve_services(data.get("services") or "clarify")
    except ValueError as exc:
        return _respond(start_response, "400 Bad Request", {"error": str(exc)})

    if not has_api_key():
        return _respond(start_response, "503 Service Unavailable",
                        {"error": "ANTHROPIC_API_KEY is not configured on the server"})

    req = Request(
        text=text,
        services=[m.name for m in services],
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
        result = improve(req)
    except Exception as exc:  # surface SDK/network errors as a clean 502
        return _respond(start_response, "502 Bad Gateway",
                        {"error": f"generation failed: {exc}"})

    return _respond(start_response, "200 OK", {
        "text": result.text,
        "model": result.model,
        "services": [m.name for m in result.services],
        "usage": {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        },
    })
