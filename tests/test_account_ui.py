"""The signed-in account settings surface: dictionary + voice management."""

import io
import json

from write_better.platform import accounts
from write_better.platform.account_ui import make_account
from write_better.platform.store import Store
from write_better.platform.webauth import SESSION_COOKIE


def _setup():
    store = Store(":memory:")
    app = make_account(store)
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token = accounts.create_session(store, user["id"])
    return store, app, user, token


def _call(app, method, path, token=None, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path}
    if token:
        environ["HTTP_COOKIE"] = f"{SESSION_COOKIE}={token}"
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    blob = b"".join(out)
    ctype = cap["headers"].get("Content-Type", "")
    payload = json.loads(blob) if "json" in ctype else blob.decode()
    return cap["status"], payload


# --- the page ----------------------------------------------------------------

def test_page_prompts_signin_when_logged_out():
    _, app, _, _ = _setup()
    status, html = _call(app, "GET", "/account")
    assert status.startswith("200")
    assert "sign in" in html.lower() and "/auth/login" in html


def test_page_renders_settings_when_signed_in():
    _, app, _, token = _setup()
    status, html = _call(app, "GET", "/account", token)
    assert status.startswith("200")
    assert "Personal dictionary" in html and "Voice profile" in html
    assert "/account/dictionary" in html and "/account/voice" in html


def test_json_endpoints_require_a_session():
    _, app, _, _ = _setup()
    status, body = _call(app, "GET", "/account/dictionary")
    assert status.startswith("401")


# --- dictionary --------------------------------------------------------------

def test_dictionary_crud_over_session():
    _, app, _, token = _setup()
    assert _call(app, "GET", "/account/dictionary", token)[1] == {"terms": []}
    status, body = _call(app, "POST", "/account/dictionary", token, {"term": "Kubernetes"})
    assert status.startswith("201") and body["terms"] == ["Kubernetes"]
    assert _call(app, "POST", "/account/dictionary", token, {"term": ""})[0].startswith("400")
    status, body = _call(app, "DELETE", "/account/dictionary", token, {"term": "Kubernetes"})
    assert status.startswith("200") and body["terms"] == []
    assert _call(app, "DELETE", "/account/dictionary", token, {"term": "ghost"})[0].startswith("404")


# --- voice -------------------------------------------------------------------

def test_voice_crud_over_session():
    _, app, _, token = _setup()
    assert _call(app, "GET", "/account/voice", token)[1] == {"voice": None}
    sample = "I write short. No fluff. Plain words only, every time."
    status, body = _call(app, "PUT", "/account/voice", token, {"samples": sample})
    assert status.startswith("201")
    assert body["voice"]["samples"] == sample and body["voice"]["descriptor"]
    assert _call(app, "PUT", "/account/voice", token, {"samples": "  "})[0].startswith("400")
    status, body = _call(app, "DELETE", "/account/voice", token)
    assert status.startswith("200") and body == {"voice": None}


def test_isolation_between_users():
    store, app, user_a, token_a = _setup()
    user_b = accounts.create_user(store, "b@b.com", "supersecret", plan="pro")
    token_b = accounts.create_session(store, user_b["id"])
    _call(app, "POST", "/account/dictionary", token_a, {"term": "AcmeSecret"})
    assert _call(app, "GET", "/account/dictionary", token_b)[1] == {"terms": []}
