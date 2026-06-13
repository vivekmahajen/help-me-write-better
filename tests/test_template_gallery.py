"""Template gallery: session-authed list/run endpoints + editor wiring."""

import io
import json

from write_better.engine import Result
from write_better.modes import resolve_services
from write_better.platform import accounts
from write_better.platform.account_ui import make_account
from write_better.platform.store import Store
from write_better.platform.webauth import SESSION_COOKIE
from write_better.ui import PAGE


def _fake_engine(req):
    return Result(text="GENERATED", model="claude-haiku-4-5",
                  services=resolve_services(req.services))


def _setup():
    store = Store(":memory:")
    app = make_account(store, engine=_fake_engine)
    user = accounts.create_user(store, "a@b.com", "supersecret", plan="pro")
    token = accounts.create_session(store, user["id"])
    return app, token


def _call(app, method, path, token=None, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path.split("?")[0],
               "QUERY_STRING": path.split("?")[1] if "?" in path else ""}
    if token:
        environ["HTTP_COOKIE"] = f"{SESSION_COOKIE}={token}"
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], json.loads(b"".join(out) or b"{}")


def test_templates_list_requires_session():
    app, _ = _setup()
    assert _call(app, "GET", "/account/templates")[0].startswith("401")


def test_templates_list_and_category_filter():
    app, token = _setup()
    status, body = _call(app, "GET", "/account/templates?category=everyday", token)
    assert status.startswith("200")
    ids = {t["id"] for t in body["templates"]}
    assert "cover-letter" in ids and all(t["category"] == "everyday" for t in body["templates"])


def test_run_unknown_template_422():
    app, token = _setup()
    status, body = _call(app, "POST", "/account/templates/run", token, {"template": "nope"})
    assert status.startswith("422") and body["code"] == "unknown_template"


def test_run_missing_fields_422_echoes_schema():
    app, token = _setup()
    status, body = _call(app, "POST", "/account/templates/run", token,
                         {"template": "cover-letter", "fields": {"role": "PM"}})
    assert status.startswith("422") and body["code"] == "missing_fields"
    assert "company" in body["missing"] and body["fields"]


def test_run_renders_and_calls_engine(monkeypatch):
    import write_better.platform.account_ui as account_ui
    monkeypatch.setattr(account_ui, "has_api_key", lambda: True)
    app, token = _setup()
    status, body = _call(app, "POST", "/account/templates/run", token,
                         {"template": "cover-letter", "fields": {
                             "role": "PM", "company": "Acme", "background": "8 yrs SaaS"}})
    assert status.startswith("200")
    assert body["text"] == "GENERATED" and body["template"] == "cover-letter"


def test_editor_has_gallery_wiring():
    assert 'id="templates"' in PAGE and 'id="gallery"' in PAGE
    assert "/account/templates" in PAGE and "/account/templates/run" in PAGE
    assert "renderTplFields" in PAGE and "runTemplate" in PAGE
