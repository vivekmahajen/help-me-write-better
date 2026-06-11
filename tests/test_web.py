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


def _call(method="GET", body=None, accept=None):
    environ = {"REQUEST_METHOD": method}
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


def test_browser_get_returns_html_ui():
    cap, data = _call("GET", accept="text/html,application/xhtml+xml")
    assert cap.status == "200 OK"
    content_type = dict(cap.headers)["Content-Type"]
    assert "text/html" in content_type
    assert b"<title>Help Me Write Better</title>" in data
    # tone and language are dropdowns, not free-text inputs
    assert b'<select id="tone">' in data
    assert b'<select id="language">' in data
    assert b'id="sample"' in data  # "Try a sample" button


def test_curl_get_still_returns_json():
    # No HTML in Accept -> JSON info, not the page.
    cap, data = _call("GET", accept="*/*")
    assert "application/json" in dict(cap.headers)["Content-Type"]
    assert json.loads(data)["service"] == "help-me-write-better"


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
