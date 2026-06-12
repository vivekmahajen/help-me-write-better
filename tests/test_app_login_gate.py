"""On the platform, the editor (/app) is gated behind login; public pages aren't."""

import uuid

from write_better.platform import wsgi, accounts


def _get(path, cookie=None, accept="text/html"):
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": path, "HTTP_ACCEPT": accept}
    if cookie:
        environ["HTTP_COOKIE"] = cookie
    cap = {}
    body = wsgi.app(environ, lambda s, h: cap.update(status=s, headers=dict(h)))
    return cap["status"], cap["headers"], b"".join(body)


def test_editor_redirects_to_login_when_signed_out():
    status, headers, _ = _get("/app")
    assert status.startswith("302")
    assert headers["Location"] == "/auth/login"


def test_editor_loads_when_signed_in():
    user = accounts.create_user(wsgi._store, f"{uuid.uuid4().hex}@t.com", "supersecret")
    token = accounts.create_session(wsgi._store, user["id"])
    status, _, body = _get("/app", cookie=f"wb_session={token}")
    assert status.startswith("200")
    assert b"Help Me Write Better" in body


def test_landing_stays_public():
    status, _, _ = _get("/")
    assert status.startswith("200")


def test_login_page_reachable_while_signed_out():
    status, _, _ = _get("/auth/login")
    assert status.startswith("200")
