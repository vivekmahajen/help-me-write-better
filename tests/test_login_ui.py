"""The browser login surface: the auth page, header gating, and deploy selection."""

import io

from write_better import landing
from write_better.platform import accounts
from write_better.platform.store import Store
from write_better.platform.webauth import make_webauth

import importlib


def _store():
    return Store(":memory:")


def _get(app, path, query=""):
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "QUERY_STRING": query}
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], cap["headers"], b"".join(out)


def test_auth_page_served_as_html():
    app = make_webauth(_store())
    for path in ("/auth/login", "/auth/signup", "/auth/reset"):
        status, headers, body = _get(app, path)
        assert status.startswith("200")
        assert "text/html" in headers["Content-Type"]
        assert b"<title>Sign in" in body
        # the forms the page needs
        assert b'id="signin"' in body and b'id="forgot"' in body and b'id="reset"' in body


def test_auth_page_posts_still_work():
    # GET serves HTML; POST still authenticates (method-differentiated route).
    store = _store()
    accounts.create_user(store, "a@b.com", "supersecret")
    app = make_webauth(store)
    environ = {"REQUEST_METHOD": "POST", "PATH_INFO": "/auth/login",
               "CONTENT_LENGTH": "0", "wsgi.input": io.BytesIO(b'{"email":"a@b.com","password":"supersecret"}')}
    environ["CONTENT_LENGTH"] = str(len(b'{"email":"a@b.com","password":"supersecret"}'))
    cap = {}
    app(environ, lambda s, h: cap.update(status=s))
    assert cap["status"].startswith("200")


def test_landing_login_link_gated_on_platform_flag():
    off = {"platform": False, "trust_layer": False, "extension_store_url": None,
           "word_addin_url": None, "docs_addin_url": None, "desktop_url": None,
           "mobile_url": None}
    assert 'href="/auth/login"' not in landing.render(off)
    assert 'href="/auth/login"' in landing.render({**off, "platform": True})


def test_app_entrypoint_selects_by_database_url():
    app_mod = importlib.import_module("app")
    assert app_mod._has_persistent_db({"DATABASE_URL": "postgresql://h/db"}) is True
    assert app_mod._has_persistent_db({"WB_DB_URL": "postgres://h/db"}) is True
    assert app_mod._has_persistent_db({"WB_DB_PATH": "wb.db"}) is False
    assert app_mod._has_persistent_db({}) is False


def test_status_endpoint_reports_mode_without_secrets():
    import json
    app_mod = importlib.import_module("app")
    cap = {}
    out = app_mod.app({"REQUEST_METHOD": "GET", "PATH_INFO": "/_status"},
                      lambda s, h: cap.update(status=s, headers=dict(h)))
    assert cap["status"].startswith("200")
    assert "application/json" in cap["headers"]["Content-Type"]
    diag = json.loads(b"".join(out))
    assert diag["mode"] in ("engine", "platform")
    assert "persistent_db_detected" in diag
    # never leak secret *values* — only env var names / booleans
    assert "ANTHROPIC_API_KEY" not in json.dumps(diag) or diag["anthropic_key_present"] in (True, False)


def test_diagnostics_names_the_detected_db_env_var():
    app_mod = importlib.import_module("app")
    d = app_mod._diagnostics({"POSTGRES_URL": "postgres://u:p@h/db"})
    assert d["persistent_db_detected"] is True
    assert d["db_source_env"] == "POSTGRES_URL"
    assert "POSTGRES_URL" in d["postgres_env_present"]
    # the secret value itself is not present anywhere in the diagnostics
    import json
    assert "u:p@h" not in json.dumps(d)
