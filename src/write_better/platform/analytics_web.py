"""First-party product analytics for the public landing/pricing pages.

  POST /events  {event, props}  -> record an allow-listed event (always 204)

Anonymous by design — no auth (the landing is public), no PII stored, and no
third-party trackers. Unknown events and malformed bodies are dropped silently;
the endpoint is a quiet sink that never errors back at the page. Per-IP rate
limited to blunt spam.
"""

from __future__ import annotations

import json

from ..demo import RateLimiter

# The only events the page is allowed to record (props are small + sanitised).
ALLOWED_EVENTS = frozenset({
    "landing_view", "pricing_view", "demo_run", "demo_fallback",
    "cta_click", "plan_selected",
})
_MAX_PROPS_BYTES = 512


def _client_ip(environ) -> str:
    fwd = environ.get("HTTP_X_FORWARDED_FOR")
    if fwd:
        return fwd.split(",")[0].strip()
    return environ.get("REMOTE_ADDR", "unknown")


def _read_json(environ) -> dict:
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        length = 0
    raw = environ["wsgi.input"].read(length) if length > 0 else b""
    if not raw:
        return {}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _sanitise_props(props) -> dict:
    """Keep props small and flat (str/num/bool values, capped size)."""
    if not isinstance(props, dict):
        return {}
    out = {}
    for k, v in props.items():
        if isinstance(v, (str, int, float, bool)):
            out[str(k)[:40]] = v[:120] if isinstance(v, str) else v
    if len(json.dumps(out)) > _MAX_PROPS_BYTES:
        return {}
    return out


def _no_content(start_response):
    start_response("204 No Content", [("Content-Length", "0"),
                                       ("Access-Control-Allow-Origin", "*")])
    return [b""]


def make_analytics(store, limiter=None):
    limiter = limiter or RateLimiter(limit=120, window=60.0)

    def app(environ, start_response):
        if environ.get("REQUEST_METHOD", "GET").upper() != "POST":
            return _no_content(start_response)
        if not limiter.allow(_client_ip(environ)):
            return _no_content(start_response)             # over the cap: drop
        data = _read_json(environ)
        event = str(data.get("event") or "")[:64]
        if event in ALLOWED_EVENTS:
            try:
                store.insert_analytics_event(event, _sanitise_props(data.get("props")))
            except Exception:
                pass                                       # never surface storage errors
        return _no_content(start_response)

    return app
