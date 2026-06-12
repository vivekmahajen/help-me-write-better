"""Anonymous first-party landing/pricing analytics (POST /events)."""

import io
import json

from write_better.platform.analytics_web import make_analytics
from write_better.platform.store import Store
from write_better.demo import RateLimiter


def _store():
    return Store(":memory:")


def _post(app, body, ip="1.2.3.4"):
    raw = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/events",
               "CONTENT_LENGTH": str(len(raw)), "wsgi.input": io.BytesIO(raw),
               "HTTP_X_FORWARDED_FOR": ip}
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], b"".join(out)


def test_records_allowed_event():
    store = _store()
    app = make_analytics(store)
    status, body = _post(app, {"event": "landing_view", "props": {}})
    assert status.startswith("204") and body == b""
    assert store.analytics_event_counts(0) == {"landing_view": 1}


def test_records_props_and_counts():
    store = _store()
    app = make_analytics(store)
    _post(app, {"event": "cta_click", "props": {"target": "open_editor"}})
    _post(app, {"event": "cta_click", "props": {"target": "see_api"}})
    _post(app, {"event": "demo_run"})
    counts = store.analytics_event_counts(0)
    assert counts == {"cta_click": 2, "demo_run": 1}


def test_unknown_event_is_dropped_silently():
    store = _store()
    app = make_analytics(store)
    status, _ = _post(app, {"event": "evil_inject", "props": {"x": 1}})
    assert status.startswith("204")               # still a quiet 204
    assert store.analytics_event_counts(0) == {}   # but nothing recorded


def test_malformed_body_is_safe():
    store = _store()
    app = make_analytics(store)
    status, _ = _post(app, b"{not json")
    assert status.startswith("204")
    assert store.analytics_event_counts(0) == {}


def test_props_are_sanitised_and_capped():
    store = _store()
    app = make_analytics(store)
    big = "x" * 1000
    _post(app, {"event": "cta_click", "props": {"target": big, "nested": {"a": 1}}})
    # event recorded; the oversized/nested props were dropped or trimmed
    assert store.analytics_event_counts(0) == {"cta_click": 1}


def test_rate_limited_events_are_dropped():
    store = _store()
    app = make_analytics(store, limiter=RateLimiter(limit=2, window=60.0))
    for _ in range(5):
        _post(app, {"event": "landing_view"}, ip="9.9.9.9")
    assert store.analytics_event_counts(0).get("landing_view") == 2  # only first 2


def test_get_is_noop_204():
    app = make_analytics(_store())
    cap = {}
    out = app({"REQUEST_METHOD": "GET", "PATH_INFO": "/events"},
              lambda s, h: cap.update(status=s))
    assert cap["status"].startswith("204")
    assert b"".join(out) == b""
