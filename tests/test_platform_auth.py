import io
import json
import time

import pytest

from write_better.platform import accounts
from write_better.platform.oauth import GoogleProvider
from write_better.platform.store import Store
from write_better.platform.webauth import make_webauth


@pytest.fixture
def store():
    s = Store(":memory:")
    yield s
    s.close()


# --- sessions -----------------------------------------------------------------

def test_session_create_authenticate_destroy(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token = accounts.create_session(store, user["id"])
    assert accounts.authenticate_session(store, token)["id"] == user["id"]
    accounts.destroy_session(store, token)
    assert accounts.authenticate_session(store, token) is None
    assert accounts.authenticate_session(store, None) is None


def test_expired_session_rejected(store):
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token = "deadbeef"
    # insert a session that already expired
    store.insert_session(user["id"], accounts._hash_key(token), ttl_seconds=-10)
    assert accounts.authenticate_session(store, token) is None


def test_stripe_customer_column_migrates_on_existing_db(tmp_path):
    # Build a DB, then re-open — migration is idempotent and the column exists.
    path = str(tmp_path / "wb.db")
    s1 = Store(path)
    u = accounts.create_user(s1, "a@b.com", "supersecret")
    s1.close()
    s2 = Store(path)
    s2.set_stripe_customer(u["id"], "cus_123")
    assert s2.get_user_by_stripe_customer("cus_123")["email"] == "a@b.com"
    s2.close()


# --- web auth (cookie flow) ---------------------------------------------------

def _call(app, method, path, body=None, cookie=None, query=""):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query}
    if cookie:
        environ["HTTP_COOKIE"] = cookie
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s, headers=h))
    return cap["status"], cap.get("headers", []), b"".join(out)


def _session_cookie(headers):
    for k, v in headers:
        if k == "Set-Cookie" and v.startswith("wb_session="):
            return v.split(";")[0]  # "wb_session=<token>"
    return None


def test_signup_login_me_logout(store):
    app = make_webauth(store)
    # signup sets a session cookie
    status, headers, body = _call(app, "POST", "/auth/signup",
                                  {"email": "a@b.com", "password": "supersecret"})
    assert status.startswith("201")
    cookie = _session_cookie(headers)
    assert cookie

    # /auth/me works with the cookie
    status, _, body = _call(app, "GET", "/auth/me", cookie=cookie)
    assert status.startswith("200")
    assert json.loads(body)["user"]["email"] == "a@b.com"

    # without a cookie -> 401
    assert _call(app, "GET", "/auth/me")[0].startswith("401")

    # logout clears the session
    _call(app, "POST", "/auth/logout", cookie=cookie)
    assert _call(app, "GET", "/auth/me", cookie=cookie)[0].startswith("401")


def test_login_wrong_password(store):
    app = make_webauth(store)
    accounts.create_user(store, "a@b.com", "supersecret")
    status, _, _ = _call(app, "POST", "/auth/login",
                         {"email": "a@b.com", "password": "nope"})
    assert status.startswith("401")


# --- OAuth (real flow, fake transport) ----------------------------------------

def _fake_transport(token="atok", sub="google-123", email="oauth@b.com"):
    def transport(method, url, headers, data):
        if "token" in url:
            return {"access_token": token, "token_type": "Bearer"}
        return {"sub": sub, "email": email}  # userinfo
    return transport


def test_oauth_provider_login_runs_full_flow():
    p = GoogleProvider("cid", "secret", transport=_fake_transport())
    url = p.authorize_url("xyz", "https://app/cb")
    assert "client_id=cid" in url and "state=xyz" in url and "response_type=code" in url
    identity = p.login("the-code", "https://app/cb")
    assert identity == {"subject": "google-123", "email": "oauth@b.com"}


def test_webauth_oauth_start_and_callback(store):
    provider = GoogleProvider("cid", "secret", transport=_fake_transport(sub="g1", email="x@b.com"))
    app = make_webauth(store, oauth_providers={"google": provider}, base_url="https://app.test")

    # start -> 302 + state cookie
    status, headers, _ = _call(app, "GET", "/auth/oauth/google/start")
    assert status.startswith("302")
    location = dict(headers)["Location"]
    assert location.startswith("https://accounts.google.com/")
    state_cookie = next(v.split(";")[0] for k, v in headers
                        if k == "Set-Cookie" and v.startswith("wb_oauth_state="))
    state_val = state_cookie.split("=", 1)[1]

    # callback with matching state -> creates user + session, 302 home
    status, headers, _ = _call(app, "GET", "/auth/oauth/google/callback",
                               cookie=state_cookie, query=f"code=abc&state={state_val}")
    assert status.startswith("302")
    assert _session_cookie(headers)
    # the OAuth user now exists
    assert store.get_user_by_oauth("google", "g1")["email"] == "x@b.com"


def test_webauth_oauth_state_mismatch_rejected(store):
    provider = GoogleProvider("cid", "secret", transport=_fake_transport())
    app = make_webauth(store, oauth_providers={"google": provider}, base_url="https://app.test")
    status, _, _ = _call(app, "GET", "/auth/oauth/google/callback",
                         cookie="wb_oauth_state=expected", query="code=abc&state=forged")
    assert status.startswith("400")


def test_webauth_unconfigured_provider(store):
    app = make_webauth(store, oauth_providers={})
    assert _call(app, "GET", "/auth/oauth/google/start")[0].startswith("404")


def test_oauth_user_links_to_existing_email(store):
    existing = accounts.create_user(store, "shared@b.com", "supersecret")
    user = accounts.get_or_create_oauth_user(store, "google", "sub-1", "shared@b.com")
    assert user["id"] == existing["id"]  # linked, not duplicated
