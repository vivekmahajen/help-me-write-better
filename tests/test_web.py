import io
import json

from write_better import web
from write_better.engine import Result
from write_better.modes import resolve_services


class _Capture:
    def __init__(self):
        self.status = None
        self.headers = None

    def __call__(self, status, headers):
        self.status = status
        self.headers = headers


def _call(method="GET", body=None, accept=None, path="/"):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path}
    if accept is not None:
        environ["HTTP_ACCEPT"] = accept
    if body is not None:
        raw = body if isinstance(body, (bytes, bytearray)) else json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = _Capture()
    chunks = web.app(environ, cap)
    return cap, b"".join(chunks)


def test_get_returns_service_info():
    cap, data = _call("GET")
    assert cap.status == "200 OK"
    payload = json.loads(data)
    assert payload["service"] == "help-me-write-better"
    assert "tighten" in payload["services"]
    assert "markdown" in payload["formats"]
    # samples are exposed so the UI can offer "Try a sample"
    assert payload["samples"]["correct"].strip()
    assert set(payload["samples"]) == set(payload["services"])


def test_browser_root_returns_landing_page():
    # GET / (browser) now serves the marketing landing page, not the editor.
    cap, data = _call("GET", accept="text/html,application/xhtml+xml", path="/")
    assert cap.status == "200 OK"
    assert "text/html" in dict(cap.headers)["Content-Type"]
    assert b"<h1>" in data and b"/app" in data        # links into the editor
    assert b'<select id="tone">' not in data          # editor controls are NOT here
    # Real, checkable proof only — no fabricated social proof.
    assert b"automated tests" in data


def test_app_route_returns_editor():
    # The demo editor moved to /app.
    cap, data = _call("GET", accept="text/html", path="/app")
    assert cap.status == "200 OK"
    assert "text/html" in dict(cap.headers)["Content-Type"]
    assert b"<title>Help Me Write Better</title>" in data
    assert b'<select id="tone">' in data
    assert b'<select id="language">' in data
    assert b'id="sample"' in data  # "Try a sample" button


def test_app_route_with_trailing_slash_returns_editor():
    cap, data = _call("GET", accept="text/html", path="/app/")
    assert b"<title>Help Me Write Better</title>" in data


def test_app_supports_service_preselect():
    # ?service= is honored client-side; the editor ships the preselect logic.
    cap, data = _call("GET", accept="text/html", path="/app")
    assert b"requestedService" in data
    assert b"URLSearchParams" in data


def test_robots_txt_served():
    cap, data = _call("GET", path="/robots.txt")
    assert cap.status == "200 OK"
    assert "text/plain" in dict(cap.headers)["Content-Type"]
    assert b"User-agent: *" in data and b"Disallow: /auth/" in data


def test_sitemap_served():
    cap, data = _call("GET", path="/sitemap.xml")
    assert cap.status == "200 OK"
    assert "application/xml" in dict(cap.headers)["Content-Type"]
    assert b"<urlset" in data


def test_og_image_served():
    cap, data = _call("GET", path="/og.svg")
    assert cap.status == "200 OK"
    assert "image/svg+xml" in dict(cap.headers)["Content-Type"]
    assert b"<svg" in data


def test_landing_has_seo_metadata():
    cap, data = _call("GET", accept="text/html", path="/")
    assert b'rel="canonical"' in data
    assert b'property="og:title"' in data
    assert b'application/ld+json' in data


def test_curl_get_still_returns_json():
    # No HTML in Accept -> JSON info, not a page.
    cap, data = _call("GET", accept="*/*")
    assert "application/json" in dict(cap.headers)["Content-Type"]
    assert json.loads(data)["service"] == "help-me-write-better"


def test_json_descriptor_is_byte_for_byte_unchanged():
    # The API contract must not drift: GET (non-HTML) returns exactly _info().
    expected = json.dumps(web._info()).encode("utf-8")
    cap, data = _call("GET", accept="application/json")
    assert data == expected
    # The route does not change the descriptor, either.
    _, at_app = _call("GET", accept="application/json", path="/app")
    assert at_app == expected


def test_options_preflight_has_cors():
    cap, data = _call("OPTIONS")
    assert cap.status.startswith("204")
    header_names = {k for k, _ in cap.headers}
    assert "Access-Control-Allow-Origin" in header_names
    assert data == b""


def test_post_without_text_is_400():
    cap, data = _call("POST", {"services": "tighten"})
    assert cap.status.startswith("400")
    assert "text" in json.loads(data)["error"]


def test_post_invalid_json_is_400():
    cap, data = _call("POST", b"{not json")
    assert cap.status.startswith("400")
    assert "JSON" in json.loads(data)["error"]


def test_post_unknown_service_is_400():
    cap, data = _call("POST", {"text": "hello", "services": "bogus"})
    assert cap.status.startswith("400")
    assert "unknown service" in json.loads(data)["error"]


def test_post_unknown_format_is_400():
    cap, data = _call("POST", {"text": "hello", "format": "pdf-deluxe"})
    assert cap.status.startswith("400")


def test_post_without_api_key_is_503(monkeypatch):
    monkeypatch.setattr(web, "has_api_key", lambda: False)
    cap, data = _call("POST", {"text": "hello", "services": "tighten"})
    assert cap.status.startswith("503")


def test_demo_route_without_key_returns_sample(monkeypatch):
    monkeypatch.setattr(web, "has_api_key", lambda: False)
    cap, data = _call("POST", {"text": "their going too the store"}, path="/demo")
    assert cap.status == "200 OK"            # demo never errors out
    payload = json.loads(data)
    assert payload["fallback"] is True
    assert payload["model"] == "sample"


def test_demo_route_success_uses_engine(monkeypatch):
    from write_better.engine import Result
    monkeypatch.setattr(web, "has_api_key", lambda: True)
    monkeypatch.setattr(web, "improve", lambda req: Result(
        text="FIXED", model="claude-haiku-4-5",
        services=resolve_services("correct,tighten"), input_tokens=5, output_tokens=4))
    # fresh limiter so the assertion isn't affected by other tests
    monkeypatch.setattr(web, "_DEMO_LIMITER", web.RateLimiter(limit=5))
    cap, data = _call("POST", {"text": "their going too the store"}, path="/demo")
    payload = json.loads(data)
    assert payload["fallback"] is False
    assert payload["text"] == "FIXED"
    assert payload["services"] == ["correct", "tighten"]


def test_post_success_invokes_engine(monkeypatch):
    captured = {}

    def fake_improve(req):
        captured["req"] = req
        return Result(
            text="POLISHED",
            model="claude-haiku-4-5",
            services=resolve_services("tighten"),
            input_tokens=7,
            output_tokens=3,
        )

    monkeypatch.setattr(web, "has_api_key", lambda: True)
    monkeypatch.setattr(web, "improve", fake_improve)

    cap, data = _call("POST", {"text": "make this shorter", "services": "tighten",
                               "format": "plain", "show_changes": True})
    assert cap.status == "200 OK"
    payload = json.loads(data)
    assert payload["text"] == "POLISHED"
    assert payload["model"] == "claude-haiku-4-5"
    assert payload["services"] == ["tighten"]
    assert payload["usage"] == {"input_tokens": 7, "output_tokens": 3}
    # request was assembled from the body
    assert captured["req"].output_format == "plain"
    assert captured["req"].show_changes is True
